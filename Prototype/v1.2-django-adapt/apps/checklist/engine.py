from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation

from .lab_import.mapping import CATALOG_BY_LABEL
from .lab_import.parser import normalize_numeric
from .rules import FLAG_RULES, active_flags, as_number, field_required, referrals
from .schema import (
    ALL_ITEM_IDS,
    CURRENT_SCHEMA_VERSION,
    FIELD_RULES,
    ITEM_FIELDS,
    PATH_ITEM_IDS,
    PREOP_ITEM_IDS,
    QUESTIONNAIRES,
)
from .services import excluded_item_ids

# Free-text note per checklist item; checklist.js uses the same limit.
NOTE_MAX_LENGTH = 2000


def _option_values(rule):
    return [str(value) for value in rule.get("options", [])]


def _questionnaire_score(config, answers):
    """Sum of all answers, or None while an answer is missing or invalid."""
    values = []
    for key in config["question_keys"]:
        value = answers.get(key)
        if value is None or value == "" or str(value) not in _option_values(FIELD_RULES[key]):
            return None
        values.append(float(value))
    score = sum(values)
    return str(int(score)) if float(score).is_integer() else str(score)


def _recompute_questionnaires(answers):
    for config in QUESTIONNAIRES.values():
        answers[config["score_key"]] = _questionnaire_score(config, answers) or ""


def migrate_state(state):
    """Brings a stored state of an older schema version up to date.

    Formerly done by the browser on every load; now applied to stored states
    before they are evaluated. States of the current version pass unchanged.
    """
    if not isinstance(state, dict):
        return state
    version = state.get("schemaVersion") or 1
    if version >= CURRENT_SCHEMA_VERSION:
        return state
    state = deepcopy(state)
    checked = state.setdefault("checked", {})
    answers = state.setdefault("answers", {})
    if version < 2:
        # A former group tick cannot prove completion of its individual measures.
        for item_id in PATH_ITEM_IDS:
            if ":sub:" in item_id:
                checked.pop(item_id.split(":sub:")[0], None)
        checked.pop("t2:p-stoma:0", None)
    if version < 3:
        # Totals entered before the questionnaires became interactive cannot be
        # derived from single answers: keep them for reference, reopen the item.
        legacy = state.setdefault("legacyScores", {})
        for questionnaire_id, config in QUESTIONNAIRES.items():
            score_key = config["score_key"]
            if _questionnaire_score(config, answers) is None and str(answers.get(score_key) or "").strip():
                legacy[score_key] = answers[score_key]
                answers[score_key] = ""
                checked.pop(f"t1:{questionnaire_id}", None)
        # Older ECOG selections stored "2 = description" instead of the grade.
        ecog = answers.get("score_ecog")
        if isinstance(ecog, str) and len(ecog) > 4 and ecog[0] in "012345" and ecog[1:4] == " = ":
            answers["score_ecog"] = ecog[0]
    state["schemaVersion"] = CURRENT_SCHEMA_VERSION
    return state


def _off_step(number, rule):
    """True when the value does not fit the field's step (as the browser checks it)."""
    if "step" not in rule:
        return False
    try:
        step = Decimal(str(rule["step"]))
        base = Decimal(str(rule.get("min", 0)))
        return step > 0 and (Decimal(str(number)) - base) % step != 0
    except InvalidOperation:
        return False


def _validate_field(key, value, answers):
    rule = FIELD_RULES.get(key)
    if not rule:
        return None
    if value is None or str(value).strip() == "":
        return "Pflichtfeld." if field_required(key, rule, answers) else None

    kind = rule.get("type")
    if kind == "number":
        number = as_number(value)
        if number is None:
            return "Es wird ein Zahlenwert erwartet."
        if "min" in rule and number < float(rule["min"]):
            return f"Wert muss mindestens {rule['min']} sein."
        if "max" in rule and number > float(rule["max"]):
            return f"Wert darf höchstens {rule['max']} sein."
        if _off_step(value, rule):
            return f"Wert muss in Schritten von {rule['step']} angegeben werden."
    elif kind == "date":
        try:
            date.fromisoformat(str(value))
        except ValueError:
            return "Ungültiges Datum."
    elif kind == "select":
        if str(value) not in _option_values(rule):
            return "Ungültige Auswahl."
    return None


def validate_item(item_id, state):
    answers = state.get("answers") or {}
    errors = {}
    for key in ITEM_FIELDS.get(item_id, []):
        error = _validate_field(key, answers.get(key), answers)
        if error:
            errors[key] = error

    if item_id == "t1:laborwerte":
        labs = state.get("labs") or []
        nonempty = [row for row in labs if any(str(row.get(k, "")).strip() for k in ("type", "value", "unit"))]
        if not nonempty:
            errors["labs"] = "Mindestens einen Laborwert mit Wert und Einheit erfassen."
        elif any(not all(str(row.get(k, "")).strip() for k in ("type", "value", "unit")) for row in nonempty):
            errors["labs"] = "Jede Laborzeile benötigt Laborwert, Wert und Einheit."
        else:
            row_errors = []
            for index, row in enumerate(nonempty):
                label = str(row.get("type") or "").strip()
                value = str(row.get("value") or "").strip()
                if label not in CATALOG_BY_LABEL:
                    row_errors.append(f"Zeile {index + 1}: unbekannter Laborparameter.")
                elif label != "Anderer Wert" and normalize_numeric(value)[1] is None:
                    row_errors.append(f"Zeile {index + 1}: numerischer Wert erwartet (optional mit < oder >).")
            if row_errors:
                errors["labs"] = " ".join(row_errors)
    return errors


def _progress(checked, ids):
    total = len(ids)
    done = sum(1 for item_id in ids if checked.get(item_id))
    return round(done / total * 100) if total else 0


def _canonical_patient_label(treatment_case):
    return f"{treatment_case.patient.name} · Fall {treatment_case.case_number}"


def default_state(treatment_case):
    return {
        "patientName": _canonical_patient_label(treatment_case),
        "opDate": treatment_case.op_date.isoformat() if treatment_case.op_date else "",
        "checked": {},
        "openBlocks": {},
        "answers": {},
        "notes": {},
        "labs": [],
        "suchtmittel": [],
        "referrals": {},
        "legacyScores": {},
        "schemaVersion": CURRENT_SCHEMA_VERSION,
    }


def evaluate_state(raw_state, treatment_case):
    """Normalize and validate a complete checklist state.

    Autosave must accept incomplete work. Invalid completed items are therefore
    automatically marked incomplete instead of rejecting the complete request.
    The returned validation_errors explain what prevented completion.
    """
    source = deepcopy(raw_state) if isinstance(raw_state, dict) else {}
    base = default_state(treatment_case)
    for key in ("checked", "openBlocks", "answers", "notes", "labs", "suchtmittel", "referrals", "legacyScores"):
        value = source.get(key)
        if isinstance(base[key], dict):
            base[key] = value if isinstance(value, dict) else {}
        elif isinstance(base[key], list):
            base[key] = value if isinstance(value, list) else []
    # Patient/case identity remains authoritative in relational tables.
    base["patientName"] = _canonical_patient_label(treatment_case)
    if "opDate" in source:
        base["opDate"] = str(source.get("opDate") or "").strip()
    base["schemaVersion"] = CURRENT_SCHEMA_VERSION
    # Overlong notes are cut instead of rejected, so autosave never fails on them.
    base["notes"] = {
        item_id: note[:NOTE_MAX_LENGTH]
        for item_id, note in base["notes"].items()
        if item_id in ALL_ITEM_IDS and isinstance(note, str)
    }

    answers = base["answers"]
    _recompute_questionnaires(answers)

    # Items excluded for the case's Eingriffsart neither count nor block
    # completion. Their ticks are kept unvalidated, so they reappear unchanged
    # if the item is included again.
    excluded = excluded_item_ids(treatment_case)
    preop_ids = [item_id for item_id in PREOP_ITEM_IDS if item_id not in excluded]
    path_ids = [item_id for item_id in PATH_ITEM_IDS if item_id not in excluded]
    applicable_ids = preop_ids + path_ids

    checked = {
        item_id: bool(value)
        for item_id, value in base["checked"].items()
        if item_id in ALL_ITEM_IDS and bool(value)
    }
    validation_errors = {}
    for item_id in list(checked):
        if item_id in excluded:
            continue
        errors = validate_item(item_id, base)
        if errors:
            checked.pop(item_id, None)
            validation_errors[item_id] = errors
    base["checked"] = checked

    preop = _progress(checked, preop_ids)
    path = _progress(checked, path_ids)
    total = _progress(checked, applicable_ids)
    # A checklist without any applicable item is never complete (all([]) would be True).
    complete = bool(applicable_ids) and all(checked.get(item_id) for item_id in applicable_ids)

    height = as_number(answers.get("vital_groesse"))
    weight = as_number(answers.get("vital_gewicht"))
    bmi = round(weight / ((height / 100) ** 2), 1) if height and height > 0 and weight and weight > 0 else None
    flags = active_flags(answers)
    op_date = base["opDate"] or "[OP-Datum ergänzen]"
    context = f"Patient/in: {base['patientName']}\nZystektomie geplant am {op_date}.\n"

    summary = {
        "progress": total,
        "progressPreop": preop,
        "progressPath": path,
        "complete": complete,
        "checkedCount": sum(1 for item_id in applicable_ids if checked.get(item_id)),
        "totalCount": len(applicable_ids),
    }
    # Everything the frontend displays but must not compute itself.
    derived = {
        "bmi": bmi,
        "flags": flags,
        "flagMessages": {name: FLAG_RULES[name].message for name, active in flags.items() if active},
        "flaggedFields": sorted({key for name, active in flags.items() if active for key in FLAG_RULES[name].fields}),
        "referrals": referrals(answers, base["labs"], flags, context),
        "schemaVersion": CURRENT_SCHEMA_VERSION,
    }
    return base, summary, derived, validation_errors
