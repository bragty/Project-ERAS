"""Backend validation/progress schema, derived from ``definition.json``.

Structure only: titles and labels shown to users come from
``services.effective_definition()``, which applies the admin text overrides.
"""

from .definition import base_definition, field_key, iter_items, option_value

_DEFINITION = base_definition()

CURRENT_SCHEMA_VERSION = _DEFINITION["schemaVersion"]

PREOP_ITEM_IDS = [item["id"] for section, item in iter_items(_DEFINITION) if section == "preop"]

PATH_ITEM_IDS = [item["id"] for section, item in iter_items(_DEFINITION) if section == "path"]

ALL_ITEM_IDS = PREOP_ITEM_IDS + PATH_ITEM_IDS

ITEM_FIELDS = {item["id"]: [field_key(ref) for ref in item.get("fields", [])] for _section, item in iter_items(_DEFINITION)}

FIELD_RULES = {
    key: {
        "key": key,
        **spec,
        **({"options": [option_value(option) for option in spec["options"]]} if "options" in spec else {}),
    }
    for key, spec in _DEFINITION["fields"].items()
}

QUESTIONNAIRES = {
    item["id"].removeprefix("t1:"): {
        "score_key": item["scoring"]["scoreKey"],
        "question_keys": item["scoring"]["questions"],
    }
    for _section, item in iter_items(_DEFINITION)
    if "scoring" in item
}
