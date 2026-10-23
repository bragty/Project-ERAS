from django.db import transaction
from django.db.models import F

from .definition import apply_texts, base_definition, filter_definition, text_entries
from .models import ChecklistText
from .schema import ALL_ITEM_IDS, CURRENT_SCHEMA_VERSION, PATH_ITEM_IDS, PREOP_ITEM_IDS


def current_schema_metadata():
    """Application-facing metadata for the checklist version used by this prototype."""
    return {
        "schemaVersion": CURRENT_SCHEMA_VERSION,
        "counts": {
            "preop": len(PREOP_ITEM_IDS),
            "path": len(PATH_ITEM_IDS),
            "total": len(ALL_ITEM_IDS),
        },
    }


def excluded_item_ids(treatment_case):
    """Checklist items that do not apply to the case's Eingriffsart."""
    procedure_type = getattr(treatment_case, "procedure_type", None) if treatment_case else None
    return set(procedure_type.excluded_item_ids) if procedure_type else set()


def effective_definition(treatment_case=None):
    """The checklist for a case: admin texts applied, items excluded for its
    Eingriffsart removed. Without a case, the full checklist."""
    overrides = dict(
        ChecklistText.objects.exclude(text=F("default_text")).values_list("key", "text")
    )
    definition = apply_texts(base_definition(), overrides) if overrides else base_definition()
    excluded = excluded_item_ids(treatment_case)
    return filter_definition(definition, excluded) if excluded else definition


@transaction.atomic
def sync_checklist_texts():
    """Mirrors the texts of ``definition.json`` into ChecklistText rows.

    New texts are added, texts of removed items deleted. When a code default
    changes, rows that were never edited follow it; edited rows keep their text
    and only get the new default for reference.
    """
    entries = text_entries()
    existing = {row.key: row for row in ChecklistText.objects.all()}
    created, updated = [], []
    for position, entry in enumerate(entries):
        row = existing.pop(entry["key"], None)
        if row is None:
            created.append(ChecklistText(position=position, default_text=entry["text"], **entry))
            continue
        before = (row.position, row.kind, row.section, row.location, row.default_text, row.text)
        if not row.is_customized:
            row.text = entry["text"]
        row.position = position
        row.kind = entry["kind"]
        row.section = entry["section"]
        row.location = entry["location"]
        row.default_text = entry["text"]
        if before != (row.position, row.kind, row.section, row.location, row.default_text, row.text):
            updated.append(row)
    ChecklistText.objects.bulk_create(created)
    ChecklistText.objects.bulk_update(updated, ["position", "kind", "section", "location", "default_text", "text"])
    ChecklistText.objects.filter(key__in=existing).delete()
    return {"created": len(created), "updated": len(updated), "deleted": len(existing)}
