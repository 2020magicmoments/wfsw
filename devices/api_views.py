from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import Device, DeviceLog
from .serializers import (
    DeviceSerializer, 
    DeviceControlSerializer, 
    DeviceLogSerializer,
    UserSerializer
)
from mqtt_service.client import get_mqtt_client
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from .throttles import DeviceControlRateThrottle
import re
from django.utils.html import escape

# ── 1. USER PROFILE API ──
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_user_profile(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


# ── 2. LIST ALL DEVICES API ──
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_device_list(request):
    devices = Device.objects.filter(user=request.user).select_related('device_type')
    serializer = DeviceSerializer(devices, many=True)
    return Response({
        'total_devices': devices.count(),
        'online_devices': devices.filter(is_online=True).count(),
        'devices': serializer.data
    })


# ── 3. ADD DEVICE API ──
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_add_device(request):
    serializer = DeviceSerializer(data=request.data)
    if serializer.is_valid():
        unique_id = serializer.validated_data['unique_device_id'].lower()

        # Uniqueness Check
        if Device.objects.filter(unique_device_id=unique_id).exists():
            return Response(
                {'error': 'Device with this ID is already registered.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        device = serializer.save(
            user=request.user, 
            unique_device_id=unique_id,
            current_state={'relay_1': 'OFF', 'relay_2': 'OFF', 'power': 'OFF'}
        )
        return Response(DeviceSerializer(device).data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def clean_device_input(unique_device_id, name):
    clean_id = unique_device_id.strip().lower()
    clean_name = escape(name.strip())  # Sanitizes HTML tags to prevent XSS attacks

    if not re.match(r'^esp32-[a-f0-9]{12}$', clean_id):
        raise ValueError("Invalid Device ID format. Must be esp32- followed by 12 hex characters.")

    return clean_id, clean_name

# ── 4. GET SINGLE DEVICE DETAILS API ──
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_device_detail(request, device_id):
    device = get_object_or_404(Device, id=device_id, user=request.user)
    serializer = DeviceSerializer(device)
    return Response(serializer.data)


# ── 5. CONTROL DEVICE API (TRIGGERS MQTT & WEBSOCKET) ──
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([DeviceControlRateThrottle])
def api_control_device(request, device_id):
    device = get_object_or_404(Device, id=device_id, user=request.user)
    serializer = DeviceControlSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    action = serializer.validated_data['action']
    relay_number = serializer.validated_data['relay_number']

    # 1. Publish command via MQTT to HiveMQ Cloud
    mqtt = get_mqtt_client()
    success = mqtt.publish_relay_command(
        device_id=device.unique_device_id,
        action=action,
        relay_number=relay_number
    )

    # 2. Update local state
    state = device.current_state or {}
    state[f'relay_{relay_number}'] = action
    if relay_number == 1:
        state['power'] = action
    device.current_state = state
    device.save(update_fields=['current_state'])

    # 3. Create Log Entry
    DeviceLog.objects.create(
        device=device,
        action=action,
        value=f'Relay {relay_number} (Mobile API)',
        performed_by=request.user,
        status='sent' if success else 'failed'
    )

    # 4. Broadcast update to WebSockets (Updates web dashboard instantly)
    mqtt._push_to_websocket(device)

    return Response({
        'status': 'success',
        'message': f'Relay {relay_number} set to {action}',
        'mqtt_delivered': success,
        'device': DeviceSerializer(device).data
    })


# ── 6. DEVICE LOGS API ──
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_device_logs(request, device_id):
    device = get_object_or_404(Device, id=device_id, user=request.user)
    logs = device.logs.all()[:30]
    serializer = DeviceLogSerializer(logs, many=True)
    return Response(serializer.data)