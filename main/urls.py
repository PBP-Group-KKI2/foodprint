from django.urls import path
from main.views import show_landing

app_name = 'main'

urlpatterns = [
    path('', show_landing, name='landing'),
]