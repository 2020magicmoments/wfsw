import time
import signal
import logging
from django.core.management.base import BaseCommand
from mqtt_service.client import get_mqtt_client

logger = logging.getLogger('mqtt_service')


class Command(BaseCommand):
    help = 'Start the MQTT listener to receive device status updates from HiveMQ Cloud'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Starting MQTT Listener...'))

        mqtt_client = get_mqtt_client()
        mqtt_client.connect()

        # Wait for connection
        time.sleep(2)

        if mqtt_client.is_connected():
            self.stdout.write(self.style.SUCCESS(
                '✅ Connected to HiveMQ Cloud! Listening for device updates...'
            ))
        else:
            self.stdout.write(self.style.ERROR(
                '❌ Failed to connect. Check your HiveMQ credentials in settings.py'
            ))

        # Graceful shutdown
        def shutdown(signum, frame):
            self.stdout.write(self.style.WARNING('\n🛑 Shutting down MQTT listener...'))
            mqtt_client.disconnect()
            self.stdout.write(self.style.SUCCESS('👋 Goodbye!'))
            exit(0)

        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)

        # Keep alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            shutdown(None, None)