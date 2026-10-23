"""Consistency check for ``definition.json``.

Registered as a Django system check, so a broken definition is reported by
``runserver``, ``migrate``, ``check`` and the test run, with the place of the
error, instead of surfacing as an empty or broken checklist page. ``custom``
blocks are rendered by the frontend and checked by ``eras/definition.test.cjs``.
"""

from numbers import Number

from django.core import checks

from .definition import base_definition, field_key, option_value
from .rules import FLAG_RULES, REQUIRED_IF

FIELD_TYPES = {"number", "date", "select", "text"}
FIELD_KEYS = {"label", "type", "options", "min", "max", "step", "placeholder", "readonly", "optional"}
ITEM_KEYS = {"id", "title", "detail", "fields", "flagRule", "custom", "questionnaire", "scoring", "widget", "scoreDescription"}
FIELD_REF_KEYS = {"key", "label", "options"}
WIDGETS = {"bmi"}


def _is_text(value):
    return isinstance(value, str) and value.strip() != ""


def _check_options(options, where, errors):
    if not isinstance(options, list) or not options:
        errors.append(f"{where}: Auswahlfeld braucht mindestens eine Option.")
        return
    for option in options:
        if isinstance(option, dict):
            if set(option) != {"value", "label"} or not _is_text(option["value"]) or not _is_text(option["label"]):
                errors.append(f"{where}: Option {option!r} braucht genau 'value' und 'label' als Text.")
        elif not _is_text(option):
            errors.append(f"{where}: Option {option!r} muss ein nicht-leerer Text sein.")
    values = [option_value(option) for option in options if isinstance(option, (str, dict))]
    if len(values) != len(set(map(str, values))):
        errors.append(f"{where}: Optionswerte sind nicht eindeutig.")


def _check_field(key, spec, errors):
    where = f"Feld '{key}'"
    if not isinstance(spec, dict):
        errors.append(f"{where}: muss ein Objekt sein.")
        return
    for unknown in sorted(set(spec) - FIELD_KEYS):
        errors.append(f"{where}: unbekannte Eigenschaft '{unknown}'.")
    if not _is_text(spec.get("label")):
        errors.append(f"{where}: 'label' fehlt oder ist leer.")
    kind = spec.get("type")
    if kind not in FIELD_TYPES:
        errors.append(f"{where}: Typ {kind!r} ist unbekannt (erlaubt: {', '.join(sorted(FIELD_TYPES))}).")
    if kind == "select":
        _check_options(spec.get("options"), where, errors)
    elif "options" in spec:
        errors.append(f"{where}: 'options' ist nur bei Typ 'select' erlaubt.")
    for bound in ("min", "max"):
        if bound in spec and (not isinstance(spec[bound], Number) or isinstance(spec[bound], bool)):
            errors.append(f"{where}: '{bound}' muss eine Zahl sein.")
    if isinstance(spec.get("min"), Number) and isinstance(spec.get("max"), Number) and spec["min"] > spec["max"]:
        errors.append(f"{where}: 'min' ist grösser als 'max'.")
    if "optional" in spec and spec["optional"] is not True:
        errors.append(f"{where}: 'optional' ist entweder true oder fehlt.")
    if spec.get("optional") and key in REQUIRED_IF:
        errors.append(f"{where}: ist 'optional', hat in rules.REQUIRED_IF aber eine Pflichtbedingung.")


def _check_scoring(item, field_keys, fields, where, errors):
    scoring = item["scoring"]
    if not isinstance(scoring, dict) or set(scoring) != {"scoreKey", "max", "questions"}:
        errors.append(f"{where}: 'scoring' braucht genau 'scoreKey', 'max' und 'questions'.")
        return
    if scoring["scoreKey"] not in field_keys:
        errors.append(f"{where}: scoreKey '{scoring['scoreKey']}' ist kein Feld dieses Punkts.")
    questions = scoring["questions"] if isinstance(scoring["questions"], list) else []
    if not questions:
        errors.append(f"{where}: 'questions' braucht mindestens eine Frage.")
    possible = 0
    for question in questions:
        spec = fields.get(question)
        if question not in field_keys or spec is None:
            errors.append(f"{where}: Frage '{question}' ist kein Feld dieses Punkts.")
            continue
        try:
            possible += max(float(option_value(option)) for option in spec.get("options") or [])
        except ValueError:
            errors.append(f"{where}: Frage '{question}' braucht Zahlen als Optionswerte, damit summiert werden kann.")
            return
    if possible and scoring["max"] != possible:
        errors.append(f"{where}: 'max' ist {scoring['max']}, die Fragen ergeben höchstens {possible:g} Punkte.")


def _check_item(item, prefix, fields, used_fields, errors):
    where = f"Punkt '{item.get('id')}'"
    if not str(item.get("id", "")).startswith(prefix):
        errors.append(f"{where}: ID muss mit '{prefix}' beginnen.")
    for unknown in sorted(set(item) - ITEM_KEYS):
        errors.append(f"{where}: unbekannte Eigenschaft '{unknown}'.")
    if not _is_text(item.get("title")):
        errors.append(f"{where}: 'title' fehlt oder ist leer.")
    detail = item.get("detail", [])
    if not isinstance(detail, list) or not all(_is_text(line) for line in detail):
        errors.append(f"{where}: 'detail' muss eine Liste nicht-leerer Texte sein.")
    keys = []
    for ref in item.get("fields", []):
        if isinstance(ref, dict):
            for unknown in sorted(set(ref) - FIELD_REF_KEYS):
                errors.append(f"{where}: Feldverweis mit unbekannter Eigenschaft '{unknown}'.")
            if "options" in ref:
                _check_options(ref["options"], f"{where}, Feld '{ref.get('key')}'", errors)
        key = field_key(ref) if isinstance(ref, (str, dict)) else None
        if key not in fields:
            errors.append(f"{where}: Feld '{key}' ist unter 'fields' nicht definiert.")
        keys.append(key)
    if len(keys) != len(set(keys)):
        errors.append(f"{where}: ein Feld ist mehrfach eingetragen.")
    used_fields.update(keys)
    if "flagRule" in item and item["flagRule"] not in FLAG_RULES:
        errors.append(f"{where}: flagRule {item['flagRule']!r} ist in rules.FLAG_RULES nicht definiert.")
    if "widget" in item and item["widget"] not in WIDGETS:
        errors.append(f"{where}: widget {item['widget']!r} ist unbekannt.")
    if "scoring" in item:
        _check_scoring(item, keys, fields, where, errors)


def definition_errors(definition):
    """All problems of ``definition`` as readable German messages."""
    errors = []
    if not isinstance(definition.get("schemaVersion"), int):
        errors.append("'schemaVersion' muss eine Ganzzahl sein.")
    fields = definition.get("fields")
    if not isinstance(fields, dict):
        return errors + ["'fields' fehlt."]
    for key, spec in fields.items():
        _check_field(key, spec, errors)

    ids, used_fields = [], set()

    def check_entries(entries, prefix, where):
        if not isinstance(entries, list):
            errors.append(f"{where}: Punkte müssen eine Liste sein.")
            return
        for entry in entries:
            ids.append(entry.get("id"))
            if "divider" in entry:
                if set(entry) != {"id", "divider"} or not _is_text(entry["divider"]):
                    errors.append(f"Zwischentitel '{entry.get('id')}': braucht genau 'id' und einen Text in 'divider'.")
            else:
                _check_item(entry, prefix, fields, used_fields, errors)

    check_entries(definition.get("preop"), "t1:", "Prä-OP Checkliste")
    phase_ids, role_ids = [], []
    for phase in definition.get("phases", []):
        phase_ids.append(phase.get("id"))
        if not (_is_text(phase.get("id")) and _is_text(phase.get("tag")) and _is_text(phase.get("title"))):
            errors.append(f"Phase '{phase.get('id')}': braucht 'id', 'tag' und 'title'.")
        for role in phase.get("roles", []):
            role_ids.append(role.get("id"))
            if not (_is_text(role.get("id")) and _is_text(role.get("title"))):
                errors.append(f"Berufsgruppe '{role.get('id')}': braucht 'id' und 'title'.")
            if role.get("jump") and role.get("items"):
                errors.append(f"Berufsgruppe '{role.get('id')}': Verweis-Gruppen (jump) dürfen keine Punkte haben.")
            check_entries(role.get("items"), "t2:", f"Berufsgruppe '{role.get('id')}'")

    for label, values in (("ID", ids), ("Phasen-ID", phase_ids), ("Berufsgruppen-ID", role_ids)):
        for duplicate in sorted({value for value in values if values.count(value) > 1}, key=str):
            errors.append(f"{label} '{duplicate}' kommt mehrfach vor.")
    for unused in sorted(set(fields) - used_fields):
        errors.append(f"Feld '{unused}' wird von keinem Punkt verwendet.")
    for key in sorted(set(REQUIRED_IF) - set(fields)):
        errors.append(f"rules.REQUIRED_IF: Feld '{key}' ist in definition.json nicht definiert.")
    for name, rule in FLAG_RULES.items():
        for key in sorted(set(rule.fields) - set(fields)):
            errors.append(f"rules.FLAG_RULES['{name}']: Feld '{key}' ist in definition.json nicht definiert.")
    return errors


@checks.register()
def check_checklist_definition(app_configs=None, **kwargs):
    return [
        checks.Error(message, hint="apps/checklist/definition.json korrigieren.", id="checklist.E001")
        for message in definition_errors(base_definition())
    ]
