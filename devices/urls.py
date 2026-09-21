from django.urls import path
from . import views

app_name = 'devices'

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('add/', views.add_device_view, name='add'),
    path('<int:device_id>/control/', views.device_control_view, name='control'),
    path('<int:device_id>/delete/', views.delete_device_view, name='delete'),
    path('<int:device_id>/logs/', views.device_logs_view, name='logs'),
]