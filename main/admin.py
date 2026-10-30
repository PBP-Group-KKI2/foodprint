from django.contrib import admin

from .models import Profile, WasteReport


@admin.register(WasteReport)
class WasteReportAdmin(admin.ModelAdmin):
    list_display = ("title", "reporter", "waste_type", "severity", "status", "created_at")
    list_filter = ("waste_type", "severity", "status")
    search_fields = ("title", "description", "location_name", "reporter__username")
    list_editable = ("status",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "points")
    list_filter = ("role",)
    search_fields = ("user__username", "email")
