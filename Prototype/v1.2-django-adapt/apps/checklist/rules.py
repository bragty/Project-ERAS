"""Clinical rules of the checklist: the only place where they are defined.

The engine applies them on every save; the frontend only displays the results
(``derived`` in the state API). Structure and texts of the checklist live in
``definition.json``; rules that need logic beyond field types live here.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from typing import Callable


def as_number(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def months_before(day, months):
    """Same day ``months`` months earlier, clamped to the end of the month."""
    index = day.year * 12 + day.month - 1 - months
    year, month = divmod(index, 12)
    return date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


# ----------------------------------------------------------------------------
# Conditional required fields. Fields marked "optional" in definition.json are
# never required; all other fields are required unless a condition says so.

def _smoker(answers):
    status = answers.get("raucher_status")
    return bool(status and status != "Nieraucher")


def _pneumo_disease(answers):
    disease = answers.get("pneumo_grunderkrankung")
    return bool(disease and disease != "Keine")


REQUIRED_IF: dict[str, Callable[[dict], bool]] = {
    "raucher_sistiert_seit": lambda a: str(a.get("raucher_status") or "").startswith("Ex-"),
    "raucher_menge": lambda a: a.get("raucher_status") == "Aktiver Raucher",
    "raucher_py": _smoker,
    "pneumo_letzte_kontrolle": _pneumo_disease,
    "pneumo_verschlechterung": _pneumo_disease,
    "ernaehrung_termin": lambda a: (as_number(a.get("score_nrs")) or 0) >= 3,
    "operateur_termin_datum": lambda a: a.get("operateur_termin_status") == "Ja",
}


def field_required(key, spec, answers):
    if spec.get("optional"):
        return False
    condition = REQUIRED_IF.get(key)
    return condition(answers) if condition else True


# ----------------------------------------------------------------------------
# Flags: automatic hints shown in the flag boxes of the items that name the rule
# ("flagRule" in definition.json). ``fields`` are highlighted while active.

@dataclass(frozen=True)
class FlagRule:
    check: Callable[[dict], bool]
    message: str
    fields: tuple[str, ...] = ()


def _pneumo(a):
    stopbang, epworth = as_number(a.get("score_stopbang")), as_number(a.get("score_epworth"))
    return (stopbang is not None and stopbang >= 3) or (epworth is not None and epworth >= 11)


def _ernaehrung(a):
    nrs = as_number(a.get("score_nrs"))
    return nrs is not None and nrs >= 3


def _kardio(a):
    ef, mmrc = as_number(a.get("kardio_ef")), as_number(a.get("score_mmrc"))
    return (ef is not None and ef < 50) or (mmrc is not None and mmrc >= 3)


def _tropo(a):
    pre, day1, day2 = (as_number(a.get(key)) for key in ("tropo_preop", "tropo_tag1", "tropo_tag2"))
    if pre is not None:
        return (day1 is not None and day1 - pre > 14) or (day2 is not None and day2 - pre > 14)
    return (
        (day1 is not None and day1 > 70)
        or (day2 is not None and day2 > 70)
        or (day1 is not None and day2 is not None and abs(day1 - day2) > 14)
    )


FLAG_RULES = {
    "pneumo": FlagRule(
        _pneumo,
        "STOP-BANG ≥3 oder Epworth ≥11 → Zuweisung Pneumologie zur OSAS-Abklärung empfohlen.",
        ("score_stopbang", "score_epworth"),
    ),
    "ernaehrung": FlagRule(_ernaehrung, "NRS ≥3 → Zuweisung Ernährungsberatung empfohlen.", ("score_nrs",)),
    "kardio": FlagRule(
        _kardio,
        "EF <50% oder mMRC Grad 3/4 → Zuweisung Kardiologie erforderlich.",
        ("score_mmrc", "kardio_ef"),
    ),
    "tropo": FlagRule(_tropo, "V.a. periop. Myokardinfarkt → EKG und Konsil Kardiologie veranlassen."),
}


def active_flags(answers):
    return {name: bool(rule.check(answers)) for name, rule in FLAG_RULES.items()}


# ----------------------------------------------------------------------------
# Referrals (Zuweisungen und Arbeitsliste). ``date_field`` links the referral
# date to the matching checklist field, so both always show the same date.

def _value(answers, key, empty="offen"):
    value = answers.get(key)
    return empty if value is None or str(value).strip() == "" else value


def _lufu_required(a, today):
    disease = a.get("pneumo_grunderkrankung")
    if disease == "Neuromuskuläre Erkrankung/Tetraplegie":
        return True
    if not disease or disease == "Keine":
        return False
    if a.get("pneumo_verschlechterung") == "Ja":
        return True
    try:
        last = date.fromisoformat(str(a.get("pneumo_letzte_kontrolle") or ""))
    except ValueError:
        return False
    months = 6 if disease == "Lungenfibrose/restriktive Lungenfunktion" else 12
    return last <= months_before(today, months)


def _physio_text(a, _labs):
    operation = {
        "Ja": "Zystektomie mit Anlage orthotope Ersatzblase",
        "Nein": "Zystektomie mit Anlage Ileum conduit",
    }.get(a.get("physio_neoblase"), "Eingriff ergänzen")
    extras = []
    if a.get("physio_neoblase") == "Ja":
        extras.append("Zusätzlich Beckenbodenphysiotherapie.")
    if a.get("physio_rehakur") == "Nein":
        extras.append("Zusätzlich ViTA-Reha postoperativ.")
    return " ".join([f"Bitte um Anmeldung ViTA-Reha präoperativ. Operation: {operation}. Keine Limiten.", *extras])


def _lab_summary(labs):
    return ", ".join(
        f"{row.get('type', '')}: {row.get('value', '')} {row.get('unit', '')}".strip()
        for row in labs
        if str(row.get("value", "")).strip()
    )


@dataclass(frozen=True)
class Referral:
    id: str
    label: str
    required: Callable[[dict, dict, date], bool]
    text: Callable[[dict, list], str]
    date_field: str | None = None


REFERRALS = [
    Referral(
        "anaesthesie", "Anästhesie",
        lambda a, flags, today: True,
        lambda a, labs: "Bitte um präoperative Anästhesie-Sprechstunde (PAB), wenn möglich mindestens einen Monat "
        "vor Operation und nach kardiologischen/pneumologischen Abklärungen.",
        date_field="anaesthesie_termin",
    ),
    Referral(
        "geriatrie", "Geriatrie",
        lambda a, flags, today: a.get("g8_zuweisung") == "Ja",
        lambda a, labs: f"Bitte um geriatrische Abklärung. G8-Score: {_value(a, 'score_g8')}. "
        f"Zuweisungsentscheid manuell dokumentiert: {_value(a, 'g8_zuweisung')}.",
    ),
    Referral(
        "pbm", "PBM",
        lambda a, flags, today: a.get("pbm_status") == "Eingeleitet",
        lambda a, labs: "Bitte um PBM-Optimierung gemäss Weisung „Perioperative Therapie von Anämie und Eisenmangel“. "
        f"Status: {_value(a, 'pbm_status')}. {_value(a, 'pbm_ansprechperson', '')}\nLabor: {_lab_summary(labs)}",
    ),
    Referral(
        "kardio", "Kardiologie",
        lambda a, flags, today: flags["kardio"],
        lambda a, labs: f"Bitte um präoperative kardiale Abklärung gemäss Weisung. EF: {_value(a, 'kardio_ef')} %. "
        f"mMRC: {_value(a, 'score_mmrc')}.",
    ),
    Referral(
        "rauchstopp", "Rauchstopp",
        lambda a, flags, today: a.get("raucher_status") in {"Aktiver Raucher", "Ex-Raucher, sistiert <1 Jahr"},
        lambda a, labs: "Bitte um zeitnahe Anbindung an die Rauchstoppsprechstunde vor Zystektomie. "
        f"{_value(a, 'raucher_status', 'Raucherstatus offen')}, {_value(a, 'raucher_menge')} Zigaretten/Tag, "
        f"kumulativ {_value(a, 'raucher_py')} py. Sistiert seit: {_value(a, 'raucher_sistiert_seit', 'nicht erfasst')}.",
    ),
    Referral(
        "osas", "Pneumologie OSAS",
        lambda a, flags, today: flags["pneumo"],
        lambda a, labs: "Bitte um zeitnahe Anbindung für eine OSAS-Abklärung, ggf. Initiierung einer CPAP-Therapie "
        f"vor Zystektomie. STOP-BANG: {_value(a, 'score_stopbang')}, Epworth: {_value(a, 'score_epworth')}. "
        f"NIV: {_value(a, 'pneumo_niv')}.",
    ),
    Referral(
        "lufu", "Pneumologie LuFu",
        lambda a, flags, today: _lufu_required(a, today),
        lambda a, labs: "Bitte um zeitnahe Anbindung für eine LuFu vor Zystektomie. "
        f"Grunderkrankung: {_value(a, 'pneumo_grunderkrankung')}, letzte Kontrolle: {_value(a, 'pneumo_letzte_kontrolle')}, "
        f"Verschlechterung: {_value(a, 'pneumo_verschlechterung')}.",
    ),
    Referral(
        "ernaehrung", "Ernährungsberatung",
        lambda a, flags, today: flags["ernaehrung"],
        lambda a, labs: "Bitte um Aufgebot innert 2 Wochen in die Ernährungsberatung zwecks Abklärung Ernährungszustand "
        f"und Einleitung allfälliger Optimierungsmassnahmen. NRS: {_value(a, 'score_nrs')}.",
        date_field="ernaehrung_termin",
    ),
    Referral(
        "physio", "Physiotherapie",
        lambda a, flags, today: True,
        _physio_text,
    ),
]


def referrals(answers, labs, flags, context, today=None):
    """The worklist entries with the computed indication and KISIM text."""
    today = today or date.today()
    return [
        {
            "id": referral.id,
            "label": referral.label,
            "required": bool(referral.required(answers, flags, today)),
            "text": context + referral.text(answers, labs),
            "dateField": referral.date_field,
        }
        for referral in REFERRALS
    ]
