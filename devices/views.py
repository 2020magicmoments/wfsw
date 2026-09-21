import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from .models import Device, DeviceLog
from .forms import AddDeviceForm, EditDeviceForm
from mqtt_service.client import get_mqtt_client


# ─── USER DASHBOARD ──────────────────────────────────────────
@login_required
def dashboard_view(request):
    devices = Device.objects.filter(user=request.user).select_related('device_type')

    # ── Inline ON/OFF from dashboard cards (AJAX + Form support) ──
    if request.method == 'POST':
        device_id = request.POST.get('device_id')
        action = request.POST.get('action', '').upper()
        relay_number = int(request.POST.get('relay_number', 1))

        device = get_object_or_404(Device, id=device_id, user=request.user)

        if action in ('ON', 'OFF'):
            mqtt = get_mqtt_client()
            success = mqtt.publish_relay_command(
                device_id=device.unique_device_id,
                action=action,
                relay_number=relay_number,
            )

            # Optimistic local update
            state = device.current_state or {}
            state[f'relay_{relay_number}'] = action
            if relay_number == 1:
                state['power'] = action
            device.current_state = state
            device.save(update_fields=['current_state'])

            DeviceLog.objects.create(
                device=device,
                action=action,
                value=f'Relay {relay_number}',
                performed_by=request.user,
                status='sent' if success else 'failed',
            )

            # ── 📡 BROADCAST TO ALL WEBSOCKET WINDOWS ──
            mqtt._push_to_websocket(device)

            # If AJAX request, return JSON response
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                from django.http import JsonResponse
                return JsonResponse({'status': 'success', 'action': action, 'relay': relay_number})

            if success:
                messages.success(request, f'{device.name} Relay {relay_number} → {action}')
            else:
                messages.warning(request, 'MQTT disconnected. Command saved locally.')

        return redirect('devices:dashboard')

    context = {
        'devices': devices,
        'total_devices': devices.count(),
        'online_devices': devices.filter(is_online=True).count(),
    }
    return render(request, 'devices/dashboard.html', context)


# ─── ADMIN DASHBOARD (see ALL users' devices) ────────────────
@login_required
def admin_dashboard_view(request):
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, 'Access denied. Admins only.')
        return redirect('devices:dashboard')

    devices = Device.objects.all().select_related('device_type', 'user')
    users = User.objects.all()

    context = {
        'devices': devices,
        'total_devices': devices.count(),
        'online_devices': devices.filter(is_online=True).count(),
        'total_users': users.count(),
        'users': users,
    }
    return render(request, 'devices/admin_dashboard.html', context)


# ─── ADD DEVICE ──────────────────────────────────────────────
@login_required
def add_device_view(request):
    if request.method == 'POST':
        form = AddDeviceForm(request.POST)
        if form.is_valid():
            device = form.save(commit=False)
            device.user = request.user
            device.current_state = {"power": "OFF"}
            device.save()
            messages.success(request, f'Device "{device.name}" added successfully!')
            return redirect('devices:dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AddDeviceForm()

    return render(request, 'devices/add_device.html', {'form': form})


# ─── DEVICE CONTROL (sends command via MQTT) ─────────────────
@login_required
def device_control_view(request, device_id):
    device = get_object_or_404(Device, id=device_id, user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action', '').upper()
        relay_number = int(request.POST.get('relay_number', 1))
        value = request.POST.get('value', '')

        allowed = device.device_type.available_commands.get('actions', [])
        if action not in allowed:
            messages.error(request, f'Action "{action}" not supported.')
            return redirect('devices:control', device_id=device.id)

        mqtt = get_mqtt_client()
        success = mqtt.publish_relay_command(
            device_id=device.unique_device_id,
            action=action,
            relay_number=relay_number,
        )

        # Update local state
        state = device.current_state or {}
        if action in ('ON', 'OFF'):
            state[f'relay_{relay_number}'] = action
            if relay_number == 1:
                state['power'] = action
        elif action == 'SET_SPEED':
            state['speed'] = int(value) if value.isdigit() else 0
        elif action == 'SET_DIRECTION':
            state['direction'] = value
        device.current_state = state
        device.save(update_fields=['current_state'])
        get_mqtt_client()._push_to_websocket(device)

        DeviceLog.objects.create(
            device=device,
            action=action,
            value=value or f'Relay {relay_number}',
            performed_by=request.user,
            status='sent' if success else 'failed',
        )

        if success:
            messages.success(request, f'✅ Relay {relay_number} → {action}')
        else:
            messages.warning(request, '⚠️ MQTT disconnected. Command saved locally.')

        return redirect('devices:control', device_id=device.id)

    recent_logs = device.logs.all()[:10]
    mqtt = get_mqtt_client()
    context = {
        'device': device,
        'logs': recent_logs,
        'mqtt_connected': mqtt.is_connected(),
        'relay_1': device.current_state.get('relay_1') or device.current_state.get('power', 'OFF'),
        'relay_2': device.current_state.get('relay_2', 'OFF'),
    }
    return render(request, 'devices/device_control.html', context)


# ─── DELETE DEVICE ───────────────────────────────────────────
@login_required
def delete_device_view(request, device_id):
    device = get_object_or_404(Device, id=device_id, user=request.user)

    if request.method == 'POST':
        device_name = device.name
        device.delete()
        messages.success(request, f'Device "{device_name}" removed.')
        return redirect('devices:dashboard')

    return render(request, 'devices/confirm_delete.html', {'device': device})


# ─── DEVICE LOGS ─────────────────────────────────────────────
@login_required
def device_logs_view(request, device_id):
    device = get_object_or_404(Device, id=device_id, user=request.user)
    logs = device.logs.all()[:50]
    return render(request, 'devices/device_logs.html', {
        'device': device, 'logs': logs
    })