from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, models, transaction
from django.urls import reverse
from django.utils import timezone

from main.models import WasteReport


def is_dispatcher(user):
    """Officials (profile role) and staff can work on collection tasks."""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    try:
        return user.profile.role == "OFFICIAL"
    except ObjectDoesNotExist:
        return False


class CollectionTask(models.Model):
    """An official's job to collect the waste from one report.

    The report's status follows the task:
    claim -> IN_PROGRESS, close -> RESOLVED, release -> back to REPORTED.
    """

    class Status(models.TextChoices):
        CLAIMED = "CLAIMED", "Claimed"
        IN_PROGRESS = "IN_PROGRESS", "Crew on the way"
        CLOSED = "CLOSED", "Closed"

    # One task per report, so two officials can never claim the same report.
    report = models.OneToOneField(
        WasteReport,
        on_delete=models.CASCADE,
        related_name="task",
    )
    official = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="collection_tasks",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.CLAIMED
    )
    scheduled_for = models.DateField(
        null=True,
        blank=True,
        help_text="Planned pickup date.",
    )
    notes = models.TextField(
        blank=True,
        help_text="Crew, equipment, or anything the next person should know.",
    )
    closing_note = models.TextField(blank=True)
    claimed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-claimed_at", "-pk"]

    def __str__(self):
        return f"{self.report.title} ({self.get_status_display()})"

    def get_absolute_url(self):
        return reverse("dispatch:task_detail", args=[self.pk])

    @property
    def is_open(self):
        return self.status != self.Status.CLOSED

    def can_be_managed_by(self, user):
        """The official who claimed it, or staff."""
        return user.is_authenticated and (user.pk == self.official_id or user.is_staff)

    @classmethod
    def claim(cls, report, official):
        """Returns the new task, or None if someone else got the report first."""
        try:
            with transaction.atomic():
                report = WasteReport.objects.select_for_update().get(pk=report.pk)
                if report.status != WasteReport.Status.REPORTED:
                    return None
                task = cls.objects.create(report=report, official=official)
                report.status = WasteReport.Status.IN_PROGRESS
                report.save(update_fields=["status", "updated_at"])
        except IntegrityError:
            return None
        return task

    def close(self, closing_note):
        with transaction.atomic():
            self.status = self.Status.CLOSED
            self.closing_note = closing_note
            self.closed_at = timezone.now()
            self.save()
            self._set_report_status(WasteReport.Status.RESOLVED)

    def release(self):
        """Gives the report back to the pending list and deletes the task."""
        with transaction.atomic():
            self._set_report_status(WasteReport.Status.REPORTED)
            self.delete()

    def _set_report_status(self, status):
        WasteReport.objects.filter(pk=self.report_id).update(
            status=status, updated_at=timezone.now()
        )
