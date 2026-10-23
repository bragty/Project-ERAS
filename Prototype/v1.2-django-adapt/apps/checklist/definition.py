"""Single source of the checklist structure and its editable texts.

``definition.json`` describes every item, field and section of the checklist.
Backend validation (``schema.py``) and the JavaScript frontend are both derived
from it. Item IDs are stored in saved checklist states and audit events, so they
must never change; texts may be overridden in the Django admin
(``ChecklistText``) without touching code.
"""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

DEFINITION_PATH = Path(__file__).with_name("definition.json")

# Text kinds that may not be emptied in the admin (an empty title or option
# would render as a blank row).
REQUIRED_TEXT_KINDS = {"title", "label", "option", "divider", "phase_tag", "phase_title", "role_title"}


@lru_cache(maxsize=1)
def base_definition():
    """The checklist exactly as defined in code. Treat as read-only."""
    with DEFINITION_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def option_value(option):
    return option["value"] if isinstance(option, dict) else option


def field_key(ref):
    return ref["key"] if isinstance(ref, dict) else ref


def iter_items(definition):
    """Yields (section, item) for every checkable item, dividers excluded."""
    for item in definition["preop"]:
        if "divider" not in item:
            yield "preop", item
    for phase in definition["phases"]:
        for role in phase["roles"]:
            for item in role["items"]:
                if "divider" not in item:
                    yield "path", item


def _without_items(items, excluded):
    """Drops excluded items and dividers that no longer head any item."""
    kept = [item for item in items if item.get("divider") or item["id"] not in excluded]
    return [
        item for index, item in enumerate(kept)
        if not item.get("divider") or (index + 1 < len(kept) and not kept[index + 1].get("divider"))
    ]


def filter_definition(definition, excluded_item_ids):
    """Returns a copy of ``definition`` without the excluded items.

    Roles and phases left without items disappear as well; the jump role
    (pointer to the preop tab) stays as long as its phase has content.
    """
    excluded = set(excluded_item_ids or ())
    result = deepcopy(definition)
    if not excluded:
        return result
    result["preop"] = _without_items(result["preop"], excluded)
    phases = []
    for phase in result["phases"]:
        roles = []
        for role in phase["roles"]:
            role["items"] = _without_items(role["items"], excluded)
            if role["items"] or role.get("jump"):
                roles.append(role)
        if any(not role.get("jump") for role in roles):
            phases.append({**phase, "roles": roles})
    result["phases"] = phases
    return result


def _text_slots(definition):
    """Yields every editable text as (key, kind, section, location, value, setter).

    Keys are built from stable IDs only, so an override keeps applying when
    items are reordered. Details are edited as one text with one bullet point
    per line.
    """

    def put(container, attr):
        def setter(value):
            container[attr] = value
        return setter

    def put_detail(item):
        def setter(value):
            lines = [line.strip() for line in value.splitlines() if line.strip()]
            if lines:
                item["detail"] = lines
            else:
                item.pop("detail", None)
        return setter

    def put_option(options, index):
        def setter(value):
            options[index] = {"value": option_value(options[index]), "label": value}
        return setter

    field_location = {}

    def item_slots(item, section, location):
        yield f"{item['id']}|title", "title", section, location, item["title"], put(item, "title")
        yield (f"{item['id']}|detail", "detail", section, f"{location} › Hinweise",
               "\n".join(item.get("detail", [])), put_detail(item))
        for ref in item.get("fields", []):
            field_location.setdefault(field_key(ref), (section, f"{location} › Feld"))
            if isinstance(ref, dict) and "label" in ref:
                yield (f"{item['id']}|field:{ref['key']}|label", "label", section,
                       f"{location} › Feld (abweichende Beschriftung)", ref["label"], put(ref, "label"))

    for item in definition["preop"]:
        if "divider" in item:
            yield f"{item['id']}|divider", "divider", "Prä-OP Checkliste", "Zwischentitel", item["divider"], put(item, "divider")
        else:
            yield from item_slots(item, "Prä-OP Checkliste", item["title"])

    for phase in definition["phases"]:
        section = f"{phase['tag']} – {phase['title']}"
        yield f"phase:{phase['id']}|tag", "phase_tag", section, "Phase", phase["tag"], put(phase, "tag")
        yield f"phase:{phase['id']}|title", "phase_title", section, "Phase", phase["title"], put(phase, "title")
        for role in phase["roles"]:
            yield f"role:{role['id']}|title", "role_title", section, role["title"], role["title"], put(role, "title")
            yield f"role:{role['id']}|note", "role_note", section, f"{role['title']} › Zusatz", role.get("note", ""), put(role, "note")
            for item in role["items"]:
                if "divider" in item:
                    yield (f"{item['id']}|divider", "divider", section, f"{role['title']} › Zwischentitel",
                           item["divider"], put(item, "divider"))
                else:
                    yield from item_slots(item, section, f"{role['title']} › {item['title']}")

    for key, spec in definition["fields"].items():
        section, location = field_location.get(key, ("Felder", "Feld"))
        location = f"{location} „{spec['label']}“"
        yield f"field:{key}|label", "label", section, location, spec["label"], put(spec, "label")
        if "placeholder" in spec:
            yield f"field:{key}|placeholder", "placeholder", section, f"{location} › Platzhalter", spec["placeholder"], put(spec, "placeholder")
        for index, option in enumerate(spec.get("options", [])):
            label = option["label"] if isinstance(option, dict) else option
            yield (f"field:{key}|option:{option_value(option)}", "option", section,
                   f"{location} › Auswahl", label, put_option(spec["options"], index))


def text_entries(definition=None):
    """All editable texts in document order: dicts for syncing ChecklistText."""
    return [
        {"key": key, "kind": kind, "section": section, "location": location, "text": value}
        for key, kind, section, location, value, _setter in _text_slots(definition or base_definition())
    ]


def apply_texts(definition, overrides):
    """Returns a copy of ``definition`` with ``overrides`` ({key: text}) applied.

    Unknown keys are ignored, so overrides of removed items do no harm.
    """
    result = deepcopy(definition)
    for key, _kind, _section, _location, _value, setter in _text_slots(result):
        if key in overrides:
            setter(overrides[key])
    return result
