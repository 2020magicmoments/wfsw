import json
from channels.generic.websocket import AsyncWebsocketConsumer


class DeviceStatusConsumer(AsyncWebsocketConsumer):
    """
    Handles WebSocket connections from browsers.
    Each authenticated user joins their own group.
    When a device belonging to them updates, they receive it instantly.
    """

    async def connect(self):
        self.user = self.scope['user']

        # Reject anonymous users
        if not self.user.is_authenticated:
            await self.close()
            return

        # Group name: only this user gets updates for their devices
        self.group_name = f'user_{self.user.id}_devices'

        # Join the group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': f'Connected as {self.user.username}',
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """Optional: Handle messages from browser (e.g. ping)."""
        try:
            data = json.loads(text_data)
            if data.get('type') == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
        except json.JSONDecodeError:
            pass

    # ── Custom handler: called from mqtt_service when a device updates ──
    async def device_update(self, event):
        """
        Send device update to WebSocket.
        Called via channel_layer.group_send() from mqtt_service/client.py
        """
        await self.send(text_data=json.dumps({
            'type': 'device_update',
            'device_id': event['device_id'],
            'unique_device_id': event['unique_device_id'],
            'is_online': event['is_online'],
            'current_state': event['current_state'],
        }))


class AdminStatusConsumer(AsyncWebsocketConsumer):
    """
    Special consumer for admins to receive updates for ALL devices.
    """

    async def connect(self):
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close()
            return

        if not (self.user.is_superuser or self.user.is_staff):
            await self.close()
            return

        self.group_name = 'admin_all_devices'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def device_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'device_update',
            'device_id': event['device_id'],
            'unique_device_id': event['unique_device_id'],
            'user_id': event['user_id'],
            'is_online': event['is_online'],
            'current_state': event['current_state'],
        }))