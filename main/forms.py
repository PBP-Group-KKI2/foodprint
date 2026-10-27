from django import forms

from .models import WasteReport
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Profile


class WasteReportForm(forms.ModelForm):

    class Meta:
        model = WasteReport
        fields = [
            "title",
            "description",
            "waste_type",
            "severity",
            "location_name",
            "latitude",
            "longitude",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"placeholder": "e.g. Leftover rice dumped behind the canteen"}
            ),
            "description": forms.Textarea(
                attrs={"rows": 3, "placeholder": "What did you see? How much?"}
            ),
            "location_name": forms.TextInput(
                attrs={"placeholder": "Optional landmark or address"}
            ),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
        }
        error_messages = {
            "latitude": {"required": "Click the map to pin where the waste is."},
            "longitude": {"required": "Click the map to pin where the waste is."},
        }

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 3:
            raise forms.ValidationError("Title must be at least 3 characters.")
        return title

    def clean_latitude(self):
        return round(self.cleaned_data["latitude"], 6)

    def clean_longitude(self):
        return round(self.cleaned_data["longitude"], 6)


class ReportFilterForm(forms.Form):
    """Filters for the map and list. All optional; empty means 'any'."""

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
    status = forms.ChoiceField(
        required=False,
        choices=[("", "Any status")] + list(WasteReport.Status.choices),
    )
    mine = forms.BooleanField(required=False, label="Only my reports")

# ============================================================
# PROFILE
# ============================================================

class ExtendedRegisterForm(UserCreationForm):
    # Menambahkan dropdown pilihan Role dari model Profile
    role = forms.ChoiceField(
        choices=Profile.ROLE_CHOICES, 
        required=True, 
        label="Register as",
        widget=forms.Select(attrs={'class': 'form-control'}) # Menyesuaikan dengan styling CSS jika ada
    )
    email = forms.EmailField(required=True, label="Alamat Email")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',)