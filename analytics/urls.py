from django.urls import path
from analytics.views import show_analytics, save_preset, delete_preset

app_name = 'analytics'

urlpatterns = [
    path('', show_analytics, name ='show_analytics'),
    path('save-preset/', save_preset, name='save_preset'),
    path('delete-preset/<int:preset_id>/', delete_preset, name='delete_preset'),
]