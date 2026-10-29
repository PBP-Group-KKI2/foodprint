from django.urls import path

from task_dispatch.views import (
    pending_reports,
    my_tasks,
    claim_report,
    task_detail,
    task_update,
    task_close,
    task_release,
)

# The shared navbar highlights "Tasks" when the namespace is 'dispatch'.
app_name = 'dispatch'

urlpatterns = [
    path('', pending_reports, name='pending_reports'),
    path('mine/', my_tasks, name='my_tasks'),
    path('claim/<int:report_pk>/', claim_report, name='claim_report'),
    path('<int:pk>/', task_detail, name='task_detail'),
    path('<int:pk>/edit/', task_update, name='task_update'),
    path('<int:pk>/close/', task_close, name='task_close'),
    path('<int:pk>/release/', task_release, name='task_release'),
]
