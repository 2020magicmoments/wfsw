from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from devices import api_views
from devices.throttles import LoginRateThrottle

class ThrottledTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [LoginRateThrottle]


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('devices/', include('devices.urls')),

    # ── REST API ROUTES FOR MOBILE APPS ──
    # path('api/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/login/', ThrottledTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/user/profile/', api_views.api_user_profile, name='api_user_profile'),
    
    path('api/devices/', api_views.api_device_list, name='api_device_list'),
    path('api/devices/add/', api_views.api_add_device, name='api_add_device'),
    path('api/devices/<int:device_id>/', api_views.api_device_detail, name='api_device_detail'),
    path('api/devices/<int:device_id>/control/', api_views.api_control_device, name='api_control_device'),
    path('api/devices/<int:device_id>/logs/', api_views.api_device_logs, name='api_device_logs'),

    path('', lambda request: redirect('accounts:login'), name='root'),
]