from django import forms
from django.contrib import admin, messages
from django.db.models import F
from django.utils.html import format_html

from apps.audit.services import record_event
from apps.responses.services import refresh_checklist_summary

from .definition import REQUIRED_TEXT_KINDS
from .models import ChecklistText, ProcedureType
from .schema import ALL_ITEM_IDS
from .services import effective_definition


class CustomizedFilter(admin.SimpleListFilter):
    title = "angepasst"
    parameter_name = "angepasst"

    def lookups(self, request, model_admin):
        return (("ja", "Ja"), ("nein", "Nein"))

    def queryset(self, request, queryset):
        if self.value() == "ja":
            return queryset.exclude(text=F("default_text"))
        if self.value() == "nein":
            return queryset.filter(text=F("default_text"))
        return queryset


class ChecklistTextForm(forms.ModelForm):
    class Meta:
        model = ChecklistText
        fields = ("text",)
        widgets = {"text": forms.Textarea(attrs={"rows": 4, "cols": 100})}

    def clean_text(self):
        text = self.cleaned_data["text"].strip()
        if not text and self.instance.kind in REQUIRED_TEXT_KINDS:
            raise forms.ValidationError("Dieser Text darf nicht leer sein.")
        return text


@admin.register(ChecklistText)
class ChecklistTextAdmin(admin.ModelAdmin):
    """Only texts are editable. Structure, IDs and rules stay in definition.json,
    so saved checklists and audit entries remain valid after every change."""

    form = ChecklistTextForm
    list_display = ("location", "kind", "short_text", "customized")
    list_filter = (CustomizedFilter, "kind", "section")
    search_fields = ("text", "default_text", "location")
    list_per_page = 100
    fields = ("section", "location", "kind", "text", "default_text_display", "help", "updated_at")
    readonly_fields = ("section", "location", "kind", "default_text_display", "help", "updated_at")
    actions = ("reset_to_default",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Text")
    def short_text(self, obj):
        return obj.text if len(obj.text) <= 120 else obj.text[:117] + "…"

    @admin.display(description="angepasst", boolean=True)
    def customized(self, obj):
        return obj.is_customized

    @admin.display(description="Standardtext (aus dem Code)")
    def default_text_display(self, obj):
        return format_html('<div style="white-space: pre-wrap">{}</div>', obj.default_text or "–")

    @admin.display(description="Hinweis")
    def help(self, obj):
        if obj.kind == ChecklistText.Kind.DETAIL:
            return "Ein Aufzählungspunkt pro Zeile. Leer lassen, um keine Hinweise anzuzeigen. Links: [Linktext](https://…)"
        if obj.kind == ChecklistText.Kind.OPTION:
            return "Nur die angezeigte Beschriftung ändert sich; gespeicherte Antworten und Regeln bleiben gültig."
        return "Änderungen sind nach dem Neuladen der Checkliste sichtbar."

    @admin.action(description="Ausgewählte Texte auf Standardtext zurücksetzen")
    def reset_to_default(self, request, queryset):
        count = 0
        for row in queryset:
            if row.is_customized:
                row.text = row.default_text
                row.save(update_fields=["text", "updated_at"])
                count += 1
        self.message_user(request, f"{count} Text(e) zurückgesetzt.", messages.SUCCESS)


def checklist_item_choices():
    """All checklist items as grouped choices, labelled with the current texts.

    Preop dividers start a new group; inside a pathway role they prefix the
    item title (e.g. "OP-Tag: Neben dem Bett gestanden …").
    """
    definition = effective_definition()
    groups = [("Prä-OP Checkliste", [])]
    for item in definition["preop"]:
        if item.get("divider"):
            groups.append((f"Prä-OP Checkliste – {item['divider']}", []))
        else:
            groups[-1][1].append((item["id"], item["title"]))
    for phase in definition["phases"]:
        for role in phase["roles"]:
            choices, divider = [], ""
            for item in role["items"]:
                if item.get("divider"):
                    divider = item["divider"]
                else:
                    choices.append((item["id"], f"{divider}: {item['title']}" if divider else item["title"]))
            groups.append((f"{phase['tag']} {phase['title']} – {role['title']}", choices))
    return [group for group in groups if group[1]]


class ProcedureTypeForm(forms.ModelForm):
    included_items = forms.MultipleChoiceField(
        label="Enthaltene Checklistenpunkte",
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Nur angehakte Punkte erscheinen in der Checkliste von Fällen dieser Eingriffsart "
        "und zählen für Fortschritt und Abschluss. Neue Punkte sind automatisch enthalten.",
    )

    class Meta:
        model = ProcedureType
        fields = ("name", "position", "active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["included_items"].choices = checklist_item_choices()
        excluded = set(self.instance.excluded_item_ids or [])
        self.fields["included_items"].initial = [item_id for item_id in ALL_ITEM_IDS if item_id not in excluded]

    def clean_included_items(self):
        included = self.cleaned_data["included_items"]
        if not included:
            # Without any item a case would count as complete right away.
            raise forms.ValidationError("Mindestens ein Checklistenpunkt muss enthalten sein.")
        return included

    def save(self, commit=True):
        included = set(self.cleaned_data["included_items"])
        self.instance.excluded_item_ids = [item_id for item_id in ALL_ITEM_IDS if item_id not in included]
        return super().save(commit)


@admin.register(ProcedureType)
class ProcedureTypeAdmin(admin.ModelAdmin):
    """Which checklist items apply per Eingriffsart. Default: all of them."""

    form = ProcedureTypeForm
    list_display = ("name", "item_count", "case_count", "active", "position")
    list_editable = ("active", "position")
    fieldsets = (
        (None, {"fields": ("name", "position", "active")}),
        ("Checkliste", {"fields": ("included_items",)}),
    )

    @admin.display(description="Checklistenpunkte")
    def item_count(self, obj):
        excluded = set(obj.excluded_item_ids or [])
        return f"{sum(1 for item_id in ALL_ITEM_IDS if item_id not in excluded)} von {len(ALL_ITEM_IDS)}"

    @admin.display(description="Fälle")
    def case_count(self, obj):
        return obj.cases.count()

    def save_model(self, request, obj, form, change):
        before = set(ProcedureType.objects.get(pk=obj.pk).excluded_item_ids) if change else set()
        super().save_model(request, obj, form, change)
        after = set(obj.excluded_item_ids)
        if before == after:
            return
        record_event(
            event_type="procedure_type_items_changed",
            entity_type="ProcedureType",
            entity_id=obj.pk,
            metadata={"name": obj.name, "excludedAdded": sorted(after - before), "excludedRemoved": sorted(before - after)},
        )
        # Stored progress of running cases follows the new configuration;
        # archived cases keep the state they were completed with.
        cases = obj.cases.filter(archived=False)
        for case in cases.select_related("procedure_type", "patient"):
            refresh_checklist_summary(case)
        if cases.exists():
            self.message_user(request, f"Fortschritt von {cases.count()} laufenden Fall/Fällen neu berechnet.", messages.INFO)
