import json

from django.contrib import admin
from django.utils.html import format_html

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    """The audit trail is append-only: it can be inspected but never changed."""

    list_display = ("created_at", "event_type", "treatment_case", "entity_type", "entity_id")
    list_filter = ("event_type", "entity_type", "created_at")
    search_fields = ("event_type", "entity_id", "treatment_case__case_number")
    date_hierarchy = "created_at"
    list_select_related = ("treatment_case__patient",)
    fields = ("created_at", "event_type", "treatment_case", "entity_type", "entity_id", "pretty_metadata")
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Metadaten")
    def pretty_metadata(self, obj):
        return format_html(
            "<pre>{}</pre>",
            json.dumps(obj.metadata, indent=2, ensure_ascii=False, sort_keys=True),
        )
