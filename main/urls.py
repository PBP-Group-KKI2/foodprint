from django.urls import path
from main.views import (
    show_landing,
    register,
    login_user,
    logout_user,
    report_map,
    report_list_json,
    report_create,
    report_detail,
    report_update,
    report_delete,
)

app_name = 'main'

urlpatterns = [
    path('', show_landing, name='landing'),
    path('register/', register, name='register'),
    path('login/', login_user, name='login'),
    path('logout/', logout_user, name='logout'),

    # Reporting & Mapping
    path('reports/', report_map, name='report_map'),
    path('reports/api/', report_list_json, name='report_list_json'),
    path('reports/create/', report_create, name='report_create'),
    path('reports/<int:pk>/', report_detail, name='report_detail'),
    path('reports/<int:pk>/edit/', report_update, name='report_update'),
    path('reports/<int:pk>/delete/', report_delete, name='report_delete'),
]