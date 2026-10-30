from django.db.models.signals import post_save
from django.dispatch import receiver

from main.models import WasteReport

from .models import CollectionTask


@receiver(post_save, sender=WasteReport)
def sync_task_with_report_status(sender, instance, **kwargs):
    """Admins can change a report's status on the report edit page. Keep its task in line.

    The task methods change the report with .update(), which doesn't send post_save,
    so this only runs for edits made outside Task Dispatch.
    """
    try:
        task = instance.task
    except CollectionTask.DoesNotExist:
        return

    if instance.status == WasteReport.Status.REPORTED:
        # Reopened: drop the old task so the report is back on the pending list.
        task.delete()
    elif instance.status == WasteReport.Status.RESOLVED and task.is_open:
        task.close("Marked as resolved by an admin.")
