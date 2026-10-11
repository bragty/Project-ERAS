from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime

from .schema import (
    ALL_ITEM_IDS,
    CURRENT_SCHEMA_VERSION,
    FIELD_RULES,
    ITEM_FIELDS,
    PATH_ITEM_IDS,
    PREOP_ITEM_IDS,
    QUESTIONNAIRES,
    REFERRAL_IDS,
)
from .lab_import.mapping import CATALOG_BY_LABEL
from .lab_import.parser import normalize_numeric


def _as_number(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _option_values(rule):
    return [str(value) for value in rule.get("options", [])]


def _field_required(key, answers):
    # Explicit exceptions from the current frontend specification.
    if key.startswith("sucht_") or key in {"pbm_ansprechperson", "thrombo_eGFR"}:
        return False
    if key == "raucher_sistiert_seit":
        return str(answers.get("raucher_status") or "").startswith("Ex-")
    if key in {"raucher_menge", "raucher_py"}:
        status = answers.get("raucher_status")
        return bool(status and status != "Nieraucher" and (key != "raucher_menge" or status == "Aktiver Raucher"))
    if key.startswith("pneumo_") and key not in {"pneumo_niv", "pneumo_grunderkrankung"}:
        disease = answers.get("pneumo_grunderkrankung")
        return bool(disease and disease != "Keine")
    if key == "ernaehrung_termin":
        return (_as_number(answers.get("score_nrs")) or 0) >= 3
    if key == "operateur_termin_datum":
        return answers.get("operateur_termin_status") == "Ja"
    return True


def _recompute_questionnaires(answers):
    for config in QUESTIONNAIRES.values():
        keys = config["question_keys"]
        values = []
        complete = True
        for key in keys:
            value = answers.get(key)
            rule = FIELD_RULES[key]
            if value is None or value == "" or str(value) not in _option_values(rule):
                complete = False
                break
            values.append(float(value))
        if complete:
            score = sum(values)
            answers[config["score_key"]] = str(int(score)) if float(score).is_integer() else str(score)
        else:
            answers[config["score_key"]] = ""


def _validate_field(key, value, answers):
    rule = FIELD_RULES.get(key)
    if not rule:
        return None
    required = _field_required(key, answers)
    if value is None or str(value).strip() == "":
        return "Pflichtfeld." if required else None

    kind = rule.get("type")
    if kind == "number":
        number = _as_number(value)
        if number is None:
            return "Es wird ein Zahlenwert erwartet."
        if "min" in rule and number < float(rule["min"]):
            return f"Wert muss mindestens {rule['min']} sein."
        if "max" in rule and number > float(rule["max"]):
            return f"Wert darf höchstens {rule['max']} sein."
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


def _flag_rules(answers):
    stopbang = _as_number(answers.get("score_stopbang"))
    epworth = _as_number(answers.get("score_epworth"))
    nrs = _as_number(answers.get("score_nrs"))
    ef = _as_number(answers.get("kardio_ef"))
    mmrc = _as_number(answers.get("score_mmrc"))
    pre = _as_number(answers.get("tropo_preop"))
    day1 = _as_number(answers.get("tropo_tag1"))
    day2 = _as_number(answers.get("tropo_tag2"))

    pneumo = (stopbang is not None and stopbang >= 3) or (epworth is not None and epworth >= 11)
    ernaehrung = nrs is not None and nrs >= 3
    kardio = (ef is not None and ef < 50) or (mmrc is not None and mmrc >= 3)

    tropo = False
    if pre is not None:
        tropo = (day1 is not None and day1 - pre > 14) or (day2 is not None and day2 - pre > 14)
    else:
        tropo = (
            (day1 is not None and day1 > 70)
            or (day2 is not None and day2 > 70)
            or (day1 is not None and day2 is not None and abs(day1 - day2) > 14)
        )

    return {
        "pneumo": bool(pneumo),
        "ernaehrung": bool(ernaehrung),
        "kardio": bool(kardio),
        "tropo": bool(tropo),
    }


def _referral_required(referral_id, answers, flags, today=None):
    today = today or date.today()
    if referral_id in {"anaesthesie", "physio"}:
        return True
    if referral_id == "geriatrie":
        return answers.get("g8_zuweisung") == "Ja"
    if referral_id == "pbm":
        return answers.get("pbm_status") == "Eingeleitet"
    if referral_id == "kardio":
        return flags["kardio"]
    if referral_id == "osas":
        return flags["pneumo"]
    if referral_id == "ernaehrung":
        return flags["ernaehrung"]
    if referral_id == "rauchstopp":
        return answers.get("raucher_status") in {"Aktiver Raucher", "Ex-Raucher, sistiert <1 Jahr"}
    if referral_id == "lufu":
        disease = answers.get("pneumo_grunderkrankung")
        if disease == "Neuromuskuläre Erkrankung/Tetraplegie":
            return True
        if not disease or disease == "Keine":
            return False
        if answers.get("pneumo_verschlechterung") == "Ja":
            return True
        raw_last = answers.get("pneumo_letzte_kontrolle")
        if not raw_last:
            return False
        try:
            last = date.fromisoformat(str(raw_last))
        except ValueError:
            return False
        months = 6 if disease == "Lungenfibrose/restriktive Lungenfunktion" else 12
        # No third-party date dependency: compare year/month buckets.
        cutoff_month = today.year * 12 + today.month - months
        last_month = last.year * 12 + last.month
        return last_month < cutoff_month
    return False



def _referral_texts(state, treatment_case):
    answers = state.get("answers") or {}
    labs = state.get("labs") or []
    patient_name = treatment_case.patient.name or "[Name ergänzen]"
    op_date = treatment_case.op_date.isoformat() if treatment_case.op_date else (state.get("opDate") or "[OP-Datum ergänzen]")
    context = f"Patient/in: {patient_name}\nZystektomie geplant am {op_date}.\n"
    lab_text = ", ".join(
        f"{row.get('type', '')}: {row.get('value', '')} {row.get('unit', '')}".strip()
        for row in labs
        if str(row.get("value", "")).strip()
    )
    procedure = (
        "Zystektomie mit Anlage orthotope Ersatzblase"
        if answers.get("physio_neoblase") == "Ja"
        else "Zystektomie mit Anlage Ileum conduit"
        if answers.get("physio_neoblase") == "Nein"
        else "Eingriff ergänzen"
    )
    texts = {
        "anaesthesie": "Bitte um präoperative Anästhesie-Sprechstunde (PAB), wenn möglich mindestens einen Monat vor Operation und nach kardiologischen/pneumologischen Abklärungen.",
        "geriatrie": f"Bitte um geriatrische Abklärung. G8-Score: {answers.get('score_g8') or 'offen'}. Zuweisungsentscheid manuell dokumentiert: {answers.get('g8_zuweisung') or 'offen'}.",
        "pbm": f"Bitte um PBM-Optimierung gemäss Weisung ‘Perioperative Therapie von Anämie und Eisenmangel’. Status: {answers.get('pbm_status') or 'offen'}. {answers.get('pbm_ansprechperson') or ''}\nLabor: {lab_text}",
        "kardio": f"Bitte um präoperative kardiale Abklärung gemäss Weisung. EF: {answers.get('kardio_ef') or 'offen'} %. mMRC: {answers.get('score_mmrc') or 'offen'}.",
        "rauchstopp": f"Bitte um zeitnahe Anbindung an die Rauchstoppsprechstunde vor Zystektomie. {answers.get('raucher_status') or 'Raucherstatus offen'}, {answers.get('raucher_menge') or 'offen'} Zigaretten/Tag, kumulativ {answers.get('raucher_py') or 'offen'} py. Sistiert seit: {answers.get('raucher_sistiert_seit') or 'nicht erfasst'}.",
        "osas": f"Bitte um zeitnahe Anbindung für eine OSAS-Abklärung, ggf. Initiierung einer CPAP-Therapie vor Zystektomie. STOP-BANG: {answers.get('score_stopbang') or 'offen'}, Epworth: {answers.get('score_epworth') or 'offen'}. NIV: {answers.get('pneumo_niv') or 'offen'}.",
        "lufu": f"Bitte um zeitnahe Anbindung für eine LuFu vor Zystektomie. Grunderkrankung: {answers.get('pneumo_grunderkrankung') or 'offen'}, letzte Kontrolle: {answers.get('pneumo_letzte_kontrolle') or 'offen'}, Verschlechterung: {answers.get('pneumo_verschlechterung') or 'offen'}.",
        "ernaehrung": f"Bitte um Aufgebot innert 2 Wochen in die Ernährungsberatung zwecks Abklärung Ernährungszustand und Einleitung allfälliger Optimierungsmassnahmen. NRS: {answers.get('score_nrs') or 'offen'}.",
        "physio": f"Bitte um Anmeldung ViTA-Reha präoperativ. Operation: {procedure}. Keine Limiten. "
        + ("Zusätzlich Beckenbodenphysiotherapie. " if answers.get("physio_neoblase") == "Ja" else "")
        + ("Zusätzlich ViTA-Reha postoperativ." if answers.get("physio_rehakur") == "Nein" else ""),
    }
    return {key: context + value for key, value in texts.items()}

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

    answers = base["answers"]
    _recompute_questionnaires(answers)

    checked = {
        item_id: bool(value)
        for item_id, value in base["checked"].items()
        if item_id in ALL_ITEM_IDS and bool(value)
    }
    validation_errors = {}
    for item_id in list(checked):
        errors = validate_item(item_id, base)
        if errors:
            checked.pop(item_id, None)
            validation_errors[item_id] = errors
    base["checked"] = checked

    preop = _progress(checked, PREOP_ITEM_IDS)
    path = _progress(checked, PATH_ITEM_IDS)
    total = _progress(checked, ALL_ITEM_IDS)
    complete = all(checked.get(item_id) for item_id in ALL_ITEM_IDS)

    height = _as_number(answers.get("vital_groesse"))
    weight = _as_number(answers.get("vital_gewicht"))
    bmi = round(weight / ((height / 100) ** 2), 1) if height and height > 0 and weight and weight > 0 else None
    flags = _flag_rules(answers)
    referrals_required = {referral_id: _referral_required(referral_id, answers, flags) for referral_id in REFERRAL_IDS}

    summary = {
        "progress": total,
        "progressPreop": preop,
        "progressPath": path,
        "complete": complete,
        "checkedCount": sum(1 for item_id in ALL_ITEM_IDS if checked.get(item_id)),
        "totalCount": len(ALL_ITEM_IDS),
    }
    derived = {
        "bmi": bmi,
        "flags": flags,
        "referralsRequired": referrals_required,
        "referralTexts": _referral_texts(base, treatment_case),
        "schemaVersion": CURRENT_SCHEMA_VERSION,
    }
    return base, summary, derived, validation_errors
