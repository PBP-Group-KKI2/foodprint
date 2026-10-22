from django.urls import path
from main.views import show_landing, register, login_user, logout_user

app_name = 'main'

urlpatterns = [
    path('', show_landing, name='landing'),
    path('register/', register, name='register'),
    path('login/', login_user, name='login'),
    path('logout/', logout_user, name='logout'),
]