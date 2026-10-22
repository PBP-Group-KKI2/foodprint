from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse


class WasteReport(models.Model):

    class WasteType(models.TextChoices):
        FOOD = "FOOD", "Food waste"
        PACKAGING = "PACKAGING", "Food packaging"
        MIXED = "MIXED", "Mixed waste"
        OTHER = "OTHER", "Other"

    class Severity(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"

    class Status(models.TextChoices):
        REPORTED = "REPORTED", "Reported"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        RESOLVED = "RESOLVED", "Resolved"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="waste_reports",
    )
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    waste_type = models.CharField(
        max_length=20, choices=WasteType.choices, default=WasteType.FOOD
    )
    severity = models.CharField(
        max_length=10, choices=Severity.choices, default=Severity.MEDIUM
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.REPORTED
    )
    latitude = models.FloatField(
        validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    longitude = models.FloatField(
        validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )
    location_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional landmark or address, e.g. 'Kantin FASILKOM'.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    def get_absolute_url(self):
        return reverse("main:report_detail", args=[self.pk])

    def is_owned_by(self, user):
        return user.is_authenticated and user.pk == self.reporter_id

    def to_dict(self, user=None):
        """JSON shape used by the map's AJAX calls."""
        return {
            "id": self.pk,
            "title": self.title,
            "description": self.description,
            "waste_type": self.waste_type,
            "waste_type_label": self.get_waste_type_display(),
            "severity": self.severity,
            "severity_label": self.get_severity_display(),
            "status": self.status,
            "status_label": self.get_status_display(),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "location_name": self.location_name,
            "reporter": self.reporter.username,
            "created_at": self.created_at.isoformat(),
            "is_owner": bool(user is not None and self.is_owned_by(user)),
            "detail_url": self.get_absolute_url(),
        }
