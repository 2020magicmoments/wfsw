from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Device, DeviceType, DeviceLog


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class DeviceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceType
        fields = ['id', 'name', 'slug', 'icon', 'available_commands']


class DeviceSerializer(serializers.ModelSerializer):
    device_type_detail = DeviceTypeSerializer(source='device_type', read_only=True)
    relay_1 = serializers.SerializerMethodField()
    relay_2 = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = [
            'id', 
            'name', 
            'unique_device_id', 
            'device_type', 
            'device_type_detail', 
            'is_online', 
            'current_state', 
            'relay_1', 
            'relay_2', 
            'last_seen', 
            'added_at'
        ]
        read_only_fields = ['is_online', 'current_state', 'last_seen', 'added_at']

    def get_relay_1(self, obj):
        state = obj.current_state or {}
        return state.get('relay_1') or state.get('power', 'OFF')

    def get_relay_2(self, obj):
        state = obj.current_state or {}
        return state.get('relay_2', 'OFF')


class DeviceControlSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['ON', 'OFF', 'SET_SPEED', 'SET_DIRECTION'])
    relay_number = serializers.IntegerField(default=1, min_value=1, max_value=2)
    value = serializers.CharField(required=False, allow_blank=True, default='')


class DeviceLogSerializer(serializers.ModelSerializer):
    performed_by_username = serializers.CharField(source='performed_by.username', read_only=True)

    class Meta:
        model = DeviceLog
        fields = ['id', 'action', 'value', 'performed_by_username', 'status', 'timestamp']