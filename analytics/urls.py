from django.urls import path
from analytics.views import show_dashboard

app_name = 'analytics'

urlpatterns = [
    path('', show_dashboard, name ="show_dashboard"),
]