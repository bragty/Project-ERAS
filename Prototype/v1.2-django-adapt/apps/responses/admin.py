import json

from django.contrib import admin
from django.utils.html import format_html

from .models import ChecklistState


def _pretty_json(value):
    return format_html(
        '<pre style="white-space: pre-wrap; max-height: 40em; overflow: auto">{}</pre>',
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True),
    )


@admin.register(ChecklistState)
class ChecklistStateAdmin(admin.ModelAdmin):
    """Read-only. Checklist answers are edited exclusively in the ERAS app so that
    validation, revision handling and the audit trail always apply."""

    list_display = (
        "treatment_case",
        "revision",
        "progress_preop",
        "progress_path",
        "progress_total",
        "complete",
        "updated_at",
    )
    list_filter = ("complete", "schema_version")
    search_fields = ("treatment_case__case_number", "treatment_case__patient__name")
    list_select_related = ("treatment_case__patient",)
    fields = (
        "treatment_case",
        "schema_version",
        "revision",
        ("progress_preop", "progress_path", "progress_total"),
        "complete",
        "pretty_validation_errors",
        "pretty_state",
        "created_at",
        "updated_at",
    )
    readonly_fields = (
        "treatment_case",
        "schema_version",
        "revision",
        "progress_preop",
        "progress_path",
        "progress_total",
        "complete",
        "pretty_validation_errors",
        "pretty_state",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Validierungsfehler")
    def pretty_validation_errors(self, obj):
        return _pretty_json(obj.validation_errors)

    @admin.display(description="Checklisten-Zustand (JSON)")
    def pretty_state(self, obj):
        return _pretty_json(obj.state)
