from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/devices/status/$', consumers.DeviceStatusConsumer.as_asgi()),
    re_path(r'ws/admin/devices/$', consumers.AdminStatusConsumer.as_asgi()),
]