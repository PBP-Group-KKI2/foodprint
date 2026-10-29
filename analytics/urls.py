from django.urls import path
from analytics.views import show_dashboard, save_preset, delete_preset

app_name = 'analytics'

urlpatterns = [
    path('', show_dashboard, name ='show_dashboard'),
    path('save-preset/', save_preset, name='save_preset'),
    path('delete-preset/<int:preset_id>/', delete_preset, name='delete_preset'),
]