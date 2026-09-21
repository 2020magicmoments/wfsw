import json
import logging
import ssl
import threading
import time

import paho.mqtt.client as mqtt
from django.conf import settings
from django.utils import timezone

from .topics import get_relay_set_topic, get_wildcard_topic, parse_incoming_topic

logger = logging.getLogger('mqtt_service')

class MQTTClient:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized: return
        self._initialized = True

        # QoS 1 and Retain configs handled in publish calls
        self.client = mqtt.Client(
            client_id=settings.MQTT_CLIENT_ID,
            protocol=mqtt.MQTTv311,
            clean_session=True # Django workers should have clean sessions
        )

        self.client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
        
        if settings.MQTT_USE_TLS:
            self.client.tls_set(
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
                cert_reqs=ssl.CERT_REQUIRED,
            )

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        self._connected = False
        self._reconnect_delay = 5

    def connect(self):
        try:
            logger.info(f"Connecting to HiveMQ as {settings.MQTT_CLIENT_ID}...")
            self.client.connect(settings.MQTT_HOST, settings.MQTT_PORT, keepalive=settings.MQTT_KEEPALIVE)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")
            self._schedule_reconnect()

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
        self._connected = False

    def is_connected(self):
        return self._connected

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            logger.info("✅ Connected to HiveMQ Cloud!")
            
            # Subscribe to devices/#
            wildcard = get_wildcard_topic()
            client.subscribe(wildcard, qos=1)
            logger.info(f"📡 Subscribed to: {wildcard}")
        else:
            self._connected = False
            logger.error(f"❌ Connection refused (code {rc})")

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        if rc != 0:
            self._schedule_reconnect()

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        payload_str = msg.payload.decode('utf-8').strip()
        
        device_id, msg_type, relay_num = parse_incoming_topic(topic)
        if not device_id: return

        from devices.models import Device
        try:
            device = Device.objects.get(unique_device_id=device_id)
            
            if msg_type == "state":
                state_dict = device.current_state or {}
                relay_key = f"relay_{relay_num}"
                state_dict[relay_key] = payload_str

                if str(relay_num) == "1":
                    state_dict["power"] = payload_str

                device.current_state = state_dict
                device.is_online = True
                device.last_seen = timezone.now()
                device.save(update_fields=["current_state", "is_online", "last_seen"])

                logger.info(f"💡 Relay {relay_num} on {device_id} is now {payload_str}")

                latest_log = device.logs.filter(action=payload_str).first()
                if latest_log and latest_log.status == "sent":
                    latest_log.status = "executed"
                    latest_log.save(update_fields=["status"])

                # ── PUSH TO WEBSOCKET ──
                self._push_to_websocket(device)

            elif msg_type == "availability":
                device.is_online = (payload_str.lower() == "online")
                device.last_seen = timezone.now()
                device.save(update_fields=["is_online", "last_seen"])
                logger.info(f"📶 Device {device_id} is {payload_str}")

                # ── PUSH TO WEBSOCKET ──
                self._push_to_websocket(device)

            elif msg_type == "info":
                info_data = json.loads(payload_str)
                logger.info(f"ℹ️ Info from {device_id}: {info_data}")

        except Device.DoesNotExist:
            logger.warning(f"Message from unknown device: {device_id}. Creating as unclaimed device...")
            
            # Auto-create the device assigned to Admin (User ID 1) so it shows up in Admin Dashboard
            from django.contrib.auth.models import User
            from devices.models import DeviceType
            
            admin_user = User.objects.filter(is_superuser=True).first()
            default_type = DeviceType.objects.first()

            if admin_user and default_type:
                Device.objects.create(
                    user=admin_user,
                    unique_device_id=device_id,
                    device_type=default_type,
                    name=f"New ESP32 ({device_id[-6:]})",
                    is_online=True,
                    current_state={"power": payload_str if msg_type == "state" else "OFF"}
                )
                logger.info(f"✨ Auto-provisioned device {device_id} to Admin!")
        except Exception as e:
            logger.error(f"MQTT msg processing error: {e}")

    def publish_relay_command(self, device_id, action, relay_number=1):
        """
        Sends "ON" or "OFF" string to the device's relay/set topic.
        Auto-connects if not connected.
        """
        # ── Auto-connect fallback if web worker isn't connected yet ──
        if not self._connected:
            logger.info("MQTT not connected in web worker. Attempting auto-connection to HiveMQ...")
            self.connect()
            
            # Wait up to 3 seconds for connection to establish
            for _ in range(30):
                if self._connected:
                    break
                time.sleep(0.1)

        if not self._connected:
            logger.error("Cannot publish: MQTT connection attempt timed out!")
            return False

        topic = get_relay_set_topic(device_id, relay_number)
        payload = action.upper()  # "ON" or "OFF"

        result = self.client.publish(topic, payload, qos=1, retain=False)
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            logger.info(f"📤 Published to {topic}: '{payload}'")
            return True
        else:
            logger.error(f"Failed to publish to {topic} (rc={result.rc})")
            return False

    def _schedule_reconnect(self):
        def _reconnect():
            time.sleep(self._reconnect_delay)
            self.connect()
        threading.Thread(target=_reconnect, daemon=True).start()

    def _push_to_websocket(self, device):
        """
        Push device update to WebSocket subscribers (user + admin groups).
        """
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            channel_layer = get_channel_layer()
            if not channel_layer:
                return

            payload = {
                'type': 'device_update',
                'device_id': device.id,
                'unique_device_id': device.unique_device_id,
                'user_id': device.user_id,
                'is_online': device.is_online,
                'current_state': device.current_state,
            }

            # Push to the device owner's group
            async_to_sync(channel_layer.group_send)(
                f'user_{device.user_id}_devices',
                payload
            )

            # Also push to admin group
            async_to_sync(channel_layer.group_send)(
                'admin_all_devices',
                payload
            )

            logger.info(f"📡 WebSocket push sent for device {device.unique_device_id}")

        except Exception as e:
            logger.error(f"WebSocket push failed: {e}")

def get_mqtt_client():
    return MQTTClient()