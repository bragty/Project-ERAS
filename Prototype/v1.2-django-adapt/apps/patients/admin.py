from django.contrib import admin, messages
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html

from apps.audit.services import record_event
from apps.core.api import ApiError
from apps.responses.services import create_initial_checklist_state, refresh_checklist_summary
from apps.workflow.services import archive_case, restore_case

from .models import Patient, TreatmentCase


class TreatmentCaseInline(admin.TabularInline):
    model = TreatmentCase
    fields = ("case_number", "op_date", "procedure_type", "procedure", "surgeon", "archived")
    readonly_fields = fields
    extra = 0
    show_change_link = True
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("name", "patient_number", "case_count", "created_at")
    search_fields = ("name", "patient_number", "cases__case_number")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [TreatmentCaseInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_case_count=Count("cases"))

    @admin.display(description="Fälle", ordering="_case_count")
    def case_count(self, obj):
        return obj._case_count


@admin.register(TreatmentCase)
class TreatmentCaseAdmin(admin.ModelAdmin):
    list_display = (
        "case_number",
        "patient",
        "op_date",
        "procedure_type",
        "surgeon",
        "bene_nurse",
        "progress",
        "complete",
        "archived",
    )
    list_filter = ("archived", "procedure_type", "checklist_state__complete", "op_date")
    search_fields = (
        "case_number",
        "patient__name",
        "patient__patient_number",
        "procedure",
        "procedure_type__name",
        "surgeon",
        "bene_nurse",
    )
    date_hierarchy = "op_date"
    list_select_related = ("patient", "checklist_state", "procedure_type")
    autocomplete_fields = ("patient",)
    readonly_fields = ("id", "archived", "archived_at", "checklist_link", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("patient", "case_number", "op_date", "procedure_type", "procedure")}),
        ("Zuständigkeiten", {"fields": ("surgeon", "bene_nurse", "bene_deputy")}),
        ("Status", {"fields": ("checklist_link", "archived", "archived_at")}),
        ("Technisch", {"classes": ("collapse",), "fields": ("id", "created_at", "updated_at")}),
    )
    actions = ("archive_selected", "restore_selected")

    @admin.display(description="Fortschritt", ordering="checklist_state__progress_total")
    def progress(self, obj):
        state = getattr(obj, "checklist_state", None)
        return f"{state.progress_total} %" if state else "–"

    @admin.display(description="Komplett", boolean=True, ordering="checklist_state__complete")
    def complete(self, obj):
        state = getattr(obj, "checklist_state", None)
        return state.complete if state else False

    @admin.display(description="Checkliste")
    def checklist_link(self, obj):
        state = getattr(obj, "checklist_state", None)
        if not state:
            return "–"
        url = reverse("admin:responses_checkliststate_change", args=[state.pk])
        return format_html(
            '<a href="{}">Revision {} · {} % · {}</a>',
            url,
            state.revision,
            state.progress_total,
            "komplett" if state.complete else "offen",
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            create_initial_checklist_state(obj)
        elif "procedure_type" in form.changed_data:
            # Other Eingriffsart, other applicable checklist items.
            refresh_checklist_summary(obj)
        record_event(
            event_type="case_updated_admin" if change else "case_created_admin",
            treatment_case=obj,
            entity_type="TreatmentCase",
            entity_id=obj.id,
            metadata={"caseNumber": obj.case_number, "changedFields": sorted(form.changed_data)},
        )

    @admin.action(description="Ausgewählte Fälle archivieren (nur bei kompletter Checkliste)")
    def archive_selected(self, request, queryset):
        done, refused = 0, []
        for case in queryset.filter(archived=False):
            try:
                archive_case(case)
                done += 1
            except ApiError:
                refused.append(case.case_number)
        if done:
            self.message_user(request, f"{done} Fall/Fälle archiviert.", messages.SUCCESS)
        if refused:
            self.message_user(
                request,
                "Nicht archiviert (Checkliste unvollständig): " + ", ".join(refused),
                messages.WARNING,
            )

    @admin.action(description="Ausgewählte Fälle wiederherstellen")
    def restore_selected(self, request, queryset):
        cases = list(queryset.filter(archived=True))
        for case in cases:
            restore_case(case)
        self.message_user(request, f"{len(cases)} Fall/Fälle wiederhergestellt.", messages.SUCCESS)
