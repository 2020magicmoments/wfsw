from django.contrib import admin
from .models import DeviceType, Device, DeviceLog


@admin.register(DeviceType)
class DeviceTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'unique_device_id', 'device_type', 'user', 'is_online', 'added_at')
    list_filter = ('device_type', 'is_online')
    search_fields = ('unique_device_id', 'name', 'user__username')


@admin.register(DeviceLog)
class DeviceLogAdmin(admin.ModelAdmin):
    list_display = ('device', 'action', 'value', 'performed_by', 'status', 'timestamp')
    list_filter = ('status', 'action')