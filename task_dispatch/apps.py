from django.apps import AppConfig


class TaskDispatchConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'task_dispatch'
    verbose_name = 'Task Dispatch'

    def ready(self):
        from . import signals  # noqa: F401
