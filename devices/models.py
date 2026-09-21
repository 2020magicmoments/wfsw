from django.db import models
from django.contrib.auth.models import User


class DeviceType(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=50, default='bi-device-ssd',
                            help_text='Bootstrap icon class, e.g. bi-toggle-on')
    description = models.TextField(blank=True)
    available_commands = models.JSONField(
        default=dict,
        help_text='JSON of supported commands, e.g. {"actions": ["ON","OFF"]}'
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Device(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    unique_device_id = models.CharField(
        max_length=50,
        unique=True,
        help_text='Unique ID printed on the physical device'
    )
    device_type = models.ForeignKey(DeviceType, on_delete=models.PROTECT, related_name='devices')
    name = models.CharField(max_length=100, help_text='Friendly name, e.g. "Living Room Light"')
    is_online = models.BooleanField(default=False)
    current_state = models.JSONField(default=dict, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.name} ({self.unique_device_id})"


class DeviceLog(models.Model):
    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('executed', 'Executed'),
        ('failed', 'Failed'),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=50)          # e.g. ON, OFF, SET_SPEED
    value = models.CharField(max_length=100, blank=True)  # e.g. "75" for speed
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sent')

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.device.name} → {self.action} ({self.status})"