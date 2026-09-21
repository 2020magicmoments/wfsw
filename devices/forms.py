import re
from django import forms
from .models import Device, DeviceType
from django.utils.html import escape


class AddDeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ['unique_device_id', 'device_type', 'name']
        widgets = {
            'unique_device_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. DEV-ABC12345'
            }),
            'device_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Living Room Light'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['device_type'].queryset = DeviceType.objects.filter(is_active=True)
        self.fields['device_type'].empty_label = '-- Select Device Type --'

    def clean_unique_device_id(self):
        uid = self.cleaned_data.get('unique_device_id', '').strip().lower()

        # Format validation: esp32-<mac_address>
        if not re.match(r'^esp32-[a-f0-9]{12}$', uid):
            raise forms.ValidationError(
                "Invalid format. Must be 'esp32-' followed by a 12-character MAC address "
                "(e.g., esp32-9454c53d1e2c)."
            )

        # Uniqueness check
        if Device.objects.filter(unique_device_id=uid).exists():
            raise forms.ValidationError(
                "This ESP32 device ID is already registered."
            )

        return uid

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if len(name) < 2:
            raise forms.ValidationError("Device name must be at least 2 characters.")
        return name

    def clean_device_input(unique_device_id, name):
        clean_id = unique_device_id.strip().lower()
        clean_name = escape(name.strip())  # Sanitizes HTML tags to prevent XSS attacks

        if not re.match(r'^esp32-[a-f0-9]{12}$', clean_id):
            raise ValueError("Invalid Device ID format. Must be esp32- followed by 12 hex characters.")

        return clean_id, clean_name


class EditDeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control'
            }),
        }


