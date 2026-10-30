from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

from .models import Profile, WasteReport


class WasteReportForm(forms.ModelForm):

    class Meta:
        model = WasteReport
        fields = [
            "title",
            "description",
            "waste_type",
            "severity",
            "location_name",
            "city",
            "district",
            "latitude",
            "longitude",
        ]
        labels = {
            "city": "City",
            "district": "District (kecamatan)",
        }
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
            "city": forms.TextInput(
                attrs={"placeholder": "Filled from the pin, e.g. Depok"}
            ),
            "district": forms.TextInput(
                attrs={"placeholder": "Filled from the pin, e.g. Beji"}
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

    @staticmethod
    def _tidy(value):
        # "  jakarta   selatan " -> "jakarta selatan": one space, no edges,
        # so the same place is always stored the same way for Analytics.
        return " ".join(value.split())

    def clean_city(self):
        return self._tidy(self.cleaned_data.get("city", ""))

    def clean_district(self):
        return self._tidy(self.cleaned_data.get("district", ""))


class WasteReportAdminForm(WasteReportForm):
    """Same as WasteReportForm, plus Status, for admins on the edit page."""

    class Meta(WasteReportForm.Meta):
        fields = WasteReportForm.Meta.fields + ["status"]


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
    city = forms.ChoiceField(required=False, label="City")
    district = forms.ChoiceField(required=False, label="District")
    mine = forms.BooleanField(required=False, label="Only my reports")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dropdowns list only the cities/districts that have reports.
        self.fields["city"].choices = [("", "All cities")] + self._distinct("city")
        self.fields["district"].choices = [("", "All districts")] + self._distinct("district")

    @staticmethod
    def _distinct(field):
        values = (
            WasteReport.objects.exclude(**{field: ""})
            .values_list(field, flat=True)
            .distinct()
            .order_by(field)
        )
        return [(v, v) for v in values]

# ============================================================
# PROFILE
# ============================================================

class ExtendedRegisterForm(UserCreationForm):
    # Menambahkan dropdown pilihan Role dari model Profile
    # Officials can claim and close reports, so an admin assigns that role in /admin/.
    role = forms.ChoiceField(
        choices=[choice for choice in Profile.ROLE_CHOICES if choice[0] != 'OFFICIAL'],
        required=True, 
        label="Register as",
        widget=forms.Select(attrs={'class': 'form-control'}) # Menyesuaikan dengan styling CSS jika ada
    )
    email = forms.EmailField(required=True, label="Alamat Email")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',)