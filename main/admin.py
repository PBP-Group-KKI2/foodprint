from django.contrib import admin

from .models import WasteReport


@admin.register(WasteReport)
class WasteReportAdmin(admin.ModelAdmin):
    list_display = ("title", "reporter", "waste_type", "severity", "status", "created_at")
    list_filter = ("waste_type", "severity", "status")
    search_fields = ("title", "description", "location_name", "reporter__username")
    list_editable = ("status",)