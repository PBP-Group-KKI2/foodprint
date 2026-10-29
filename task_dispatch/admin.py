from django.contrib import admin

from .models import CollectionTask


@admin.register(CollectionTask)
class CollectionTaskAdmin(admin.ModelAdmin):
    list_display = ("report", "official", "status", "scheduled_for", "claimed_at", "closed_at")
    list_filter = ("status",)
    search_fields = ("report__title", "report__city", "official__username", "notes")
    raw_id_fields = ("report",)
