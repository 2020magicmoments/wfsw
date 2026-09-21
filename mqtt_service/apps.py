import os
import sys
from django.apps import AppConfig


class MqttServiceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mqtt_service'
    verbose_name = 'MQTT Service'

    def ready(self):
        # Only run inside the main Django worker process (prevents duplicate execution)
        if os.environ.get('RUN_MAIN') == 'true' or 'daphne' in sys.argv[0]:
            try:
                from .client import get_mqtt_client
                mqtt_client = get_mqtt_client()
                mqtt_client.connect()
                print("📡 MQTT Singleton Client auto-connected inside Django process.")
            except Exception as e:
                print(f"MQTT auto-connect error: {e}")