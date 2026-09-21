from django.conf import settings


def get_prefix():
    return settings.MQTT_TOPIC_PREFIX


def get_command_topic(user_id, device_unique_id):
    """
    Django → Device
    Example: iot_platform/5/DEV-ABC12345/command
    """
    return f"{get_prefix()}/{user_id}/{device_unique_id}/command"


def get_status_topic(user_id, device_unique_id):
    """
    Device → Django
    Example: iot_platform/5/DEV-ABC12345/status
    """
    return f"{get_prefix()}/{user_id}/{device_unique_id}/status"


def get_telemetry_topic(user_id, device_unique_id):
    """
    Device → Django (sensor data, future use)
    """
    return f"{get_prefix()}/{user_id}/{device_unique_id}/telemetry"


def get_all_status_wildcard():
    """
    Subscribe to ALL device statuses at once.
    Example: iot_platform/+/+/status
    """
    return f"{get_prefix()}/+/+/status"


def get_all_command_wildcard():
    """
    For debugging: listen to all commands.
    """
    return f"{get_prefix()}/+/+/command"


def parse_status_topic(topic):
    """
    Parse 'iot_platform/5/DEV-ABC12345/status'
    Returns: (user_id='5', device_unique_id='DEV-ABC12345')
    """
    parts = topic.split('/')
    if len(parts) >= 4:
        return parts[1], parts[2]
    return None, None

def get_relay_set_topic(device_id, relay_number=1):
    """
    Django -> ESP32: Command topic
    Example: devices/esp32-9454c53d1e2c/relay/1/set
    """
    return f"devices/{device_id}/relay/{relay_number}/set"

def get_wildcard_topic():
    """
    Subscribe to all ESP32 messages (state, info, availability).
    Example: devices/#
    """
    return "devices/#"

def parse_incoming_topic(topic):
    """
    Parses incoming topics based on the spec.
    Returns: (device_id, message_type, relay_number_or_none)
    """
    parts = topic.split('/')
    if len(parts) < 3 or parts[0] != "devices":
        return None, None, None

    device_id = parts[1]
    
    if topic.endswith("/state") and "relay" in parts:
        # devices/{device_id}/relay/{relay_number}/state
        relay_number = parts[3]
        return device_id, "state", relay_number
        
    elif topic.endswith("/availability"):
        # devices/{device_id}/availability
        return device_id, "availability", None
        
    elif topic.endswith("/info"):
        # devices/{device_id}/info
        return device_id, "info", None
        
    return None, None, None