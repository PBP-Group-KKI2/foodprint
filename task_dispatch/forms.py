from django import forms

from main.models import WasteReport

from .models import CollectionTask


class PendingFilterForm(forms.Form):
    """Filters for the pending list. All optional; empty means 'any'."""

    SORT_CHOICES = [
        ("severity", "Most severe first"),
        ("oldest", "Oldest first"),
        ("newest", "Newest first"),
    ]

    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(attrs={"placeholder": "Search title or place", "type": "search"}),
    )
    waste_type = forms.ChoiceField(
        required=False,
        label="Type",
        choices=[("", "All types")] + list(WasteReport.WasteType.choices),
    )
    severity = forms.ChoiceField(
        required=False,
        choices=[("", "Any severity")] + list(WasteReport.Severity.choices),
    )
    city = forms.ChoiceField(required=False, label="City")
    sort = forms.ChoiceField(required=False, choices=SORT_CHOICES)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only cities that still have pending reports.
        cities = (
            WasteReport.objects.filter(status=WasteReport.Status.REPORTED, task__isnull=True)
            .exclude(city="")
            .values_list("city", flat=True)
            .distinct()
            .order_by("city")
        )
        self.fields["city"].choices = [("", "All cities")] + [(c, c) for c in cities]


class TaskUpdateForm(forms.ModelForm):
    # Closing has its own form, so it isn't offered here.
    status = forms.ChoiceField(
        choices=[
            (CollectionTask.Status.CLAIMED, CollectionTask.Status.CLAIMED.label),
            (CollectionTask.Status.IN_PROGRESS, CollectionTask.Status.IN_PROGRESS.label),
        ],
    )

    class Meta:
        model = CollectionTask
        fields = ["status", "scheduled_for", "notes"]
        labels = {"scheduled_for": "Pickup date"}
        widgets = {
            "scheduled_for": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notes": forms.Textarea(
                attrs={"rows": 4, "placeholder": "e.g. Truck B, two crew members, bring gloves"}
            ),
        }


class TaskCloseForm(forms.ModelForm):

    class Meta:
        model = CollectionTask
        fields = ["closing_note"]
        labels = {"closing_note": "What was done?"}
        widgets = {
            "closing_note": forms.Textarea(
                attrs={"rows": 4, "placeholder": "e.g. Collected 3 bags, area cleaned"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["closing_note"].required = True

    def clean_closing_note(self):
        note = self.cleaned_data["closing_note"].strip()
        if len(note) < 5:
            raise forms.ValidationError("Please describe what was done (at least 5 characters).")
        return note
