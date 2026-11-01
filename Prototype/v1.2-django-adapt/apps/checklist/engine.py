from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from .lab_import.mapping import CATALOG_BY_LABEL
from .lab_import.parser import normalize_numeric
from .rules import FLAG_RULES, active_flags, as_number, field_required, referrals, cardiac_assessment, bowel_guidance
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


def _recompute_questionnaires(answers, effective_answers=None):
    for config in QUESTIONNAIRES.values():
        answers[config["score_key"]] = _questionnaire_score(config, effective_answers if effective_answers is not None else answers) or ""


def patient_answers(answers, treatment_case):
    """One authoritative context for visibility, validation and STOP-BANG.

    The legacy questionnaire answer stays stored for reference; it is never
    inferred into central patient data or used instead of a missing sex value.
    """
    return {**answers, "stopbang_sex": {"male": "1", "female": "0"}.get(treatment_case.patient.sex, "")}


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


def _validate_field(key, value, answers, *, validate_hidden=False):
    rule = FIELD_RULES.get(key)
    if not rule:
        return None
    # Hidden optional values remain stored when context changes.
    if rule.get("maleOnly") and answers.get("stopbang_sex") != "1" and not validate_hidden:
        return None
    kind = rule.get("type")
    if kind == "multiselect":
        if value is None:
            return None
        if not isinstance(value, list) or any(not isinstance(v, str) or v not in _option_values(rule) for v in value):
            return "Ungültige Mehrfachauswahl."
        if len(set(value)) != len(value):
            return "Auswahl enthält doppelte Einträge."
        return None
    if kind == "physicians":
        if value is None:
            return None
        if not isinstance(value, list) or len(value) > 50:
            return "Höchstens 50 behandelnde Ärzte erfassen."
        for row in value:
            if not isinstance(row, dict) or set(row) - {"specialty", "name"}:
                return "Ungültiger Arzteintrag."
            if any(not isinstance(v, str) or len(v) > 2000 for v in row.values()):
                return "Fachrichtung und Name müssen Texte mit höchstens 2000 Zeichen sein."
            if any(v.strip() for v in row.values()) and not all(str(row.get(k, "")).strip() for k in ("specialty", "name")):
                return "Bei jedem Arzteintrag Fachrichtung und Name ergänzen."
        return None
    if kind == "checkbox":
        return None if value in (None, "", "Ja", "Nein") else "Ungültiger Checkboxwert."
    if value is None or str(value).strip() == "":
        return "Pflichtfeld." if field_required(key, rule, answers) else None

    if isinstance(value, (dict, list, bool)):
        return "Ungültiger Feldwert."
    if kind in {"text", "textarea"} and (not isinstance(value, str) or len(value) > 2000):
        return "Text mit höchstens 2000 Zeichen erwartet."
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
            if date.fromisoformat(str(value)).isoformat() != str(value):
                raise ValueError
        except ValueError:
            return "Ungültiges Datum."
    elif kind == "select":
        if str(value) not in _option_values(rule):
            return "Ungültige Auswahl."
    return None


def parse_operation_date(raw):
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            parsed = datetime.strptime(str(raw).strip(), fmt).date()
            if parsed.strftime(fmt) == str(raw).strip():
                return parsed
        except ValueError:
            pass
    return None


def draft_errors(state, treatment_case, *, validate_hidden=False):
    """Technical errors in populated fields. Blank/incomplete work remains a draft."""
    answers = patient_answers(state.get("answers") or {}, treatment_case)
    errors = {}
    excluded = excluded_item_ids(treatment_case)
    for item_id, keys in ITEM_FIELDS.items():
        if item_id in excluded:
            continue
        for key in keys:
            value = answers.get(key)
            if FIELD_RULES[key].get("readonly") or value is None or (isinstance(value, str) and not value.strip()):
                continue
            error = _validate_field(key, value, answers, validate_hidden=validate_hidden)
            if error:
                errors.setdefault(item_id, {})[key] = error
    if state.get("opDate") and not parse_operation_date(state["opDate"]):
        errors["header"] = {"opDate": "Bitte ein gültiges OP-Datum als TT.MM.JJJJ oder JJJJ-MM-TT eingeben."}
    for referral_id, entry in (state.get("referrals") or {}).items():
        if not isinstance(entry, dict):
            errors.setdefault("referrals", {})[referral_id] = "Ungültiger Arbeitslisteneintrag."
            continue
        value = entry.get("date")
        if value:
            try:
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError
            except (TypeError, ValueError):
                errors.setdefault("referrals", {})[referral_id] = "Bitte ein gültiges Datum eingeben."
    for index, row in enumerate(state.get("labs") or []):
        if not isinstance(row, dict):
            errors.setdefault("t1:laborwerte", {})[f"lab:{index}"] = "Ungültige Laborzeile."
            continue
        label, value = row.get("type"), row.get("value")
        if (label is not None and not isinstance(label, str)) or (label and label not in CATALOG_BY_LABEL):
            errors.setdefault("t1:laborwerte", {})[f"lab:{index}:type"] = "Unbekannter Laborparameter."
        if value not in (None, "") and label != "Anderer Wert":
            _operator, numeric = normalize_numeric(value)
            if numeric is None or as_number(numeric) is None or as_number(numeric) < 0:
                errors.setdefault("t1:laborwerte", {})[f"lab:{index}:value"] = "Nichtnegativen Zahlenwert eingeben (optional mit < oder >)."
    return errors


def validate_item(item_id, state, effective_answers=None):
    answers = effective_answers if effective_answers is not None else state.get("answers") or {}
    errors = {}
    for key in ITEM_FIELDS.get(item_id, []):
        error = _validate_field(key, answers.get(key), answers)
        if error:
            errors[key] = error

    if item_id == "t1:kardio":
        assessment = cardiac_assessment(answers)
        if assessment["pending"]:
            errors["kardio_met"] = " ".join(assessment["pending"])

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
    if not treatment_case.patient.sex and answers.get("score_stopbang") not in (None, ""):
        base["legacyScores"].setdefault("score_stopbang", answers["score_stopbang"])
    _recompute_questionnaires(answers, patient_answers(answers, treatment_case))
    effective_answers = patient_answers(answers, treatment_case)

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
    validation_errors = draft_errors(base, treatment_case)
    for item_id in list(checked):
        if item_id in excluded:
            continue
        errors = validate_item(item_id, base, effective_answers)
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
        "patientSex": treatment_case.patient.sex,
        "cardiac": cardiac_assessment(answers),
        "bowel": bowel_guidance(answers, base["opDate"]),
        "bmi": bmi,
        "flags": flags,
        "flagMessages": {name: FLAG_RULES[name].message for name, active in flags.items() if active},
        "flaggedFields": sorted({key for name, active in flags.items() if active for key in FLAG_RULES[name].fields}),
        "referrals": referrals(answers, base["labs"], flags, context),
        "schemaVersion": CURRENT_SCHEMA_VERSION,
    }
    return base, summary, derived, validation_errors
