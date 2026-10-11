"""Central mapping between KISIM/report labels and the existing checklist lab options.

The current frontend stores the display label in ``STATE.labs[].type``.  Stable
``id`` values are introduced only for the import API/provenance and are mapped
back to the unchanged frontend labels.
"""
from __future__ import annotations

import re
import unicodedata

LAB_CATALOG = (
    {"id": "hb", "label": "Hb", "aliases": ("Hb", "Hämoglobin", "Haemoglobin", "Hemoglobin")},
    {"id": "leukozyten", "label": "Leukozyten", "aliases": ("Leukozyten", "Leukos", "Leuko")},
    {"id": "thrombozyten", "label": "Thrombozyten", "aliases": ("Thrombozyten", "Thrombos", "Thrombo")},
    {"id": "quick_inr", "label": "Quick / INR", "aliases": ("Quick / INR", "Quick", "INR", "Quick INR")},
    {"id": "ferritin", "label": "Ferritin", "aliases": ("Ferritin",)},
    {
        "id": "transferrinsaettigung",
        "label": "Transferrinsättigung",
        "aliases": ("Transferrinsättigung", "Transferrinsaettigung", "Transferrin-Sättigung", "TSAT"),
    },
    {"id": "kreatinin", "label": "Kreatinin", "aliases": ("Kreatinin", "Creatinin", "Creatinine")},
    {"id": "natrium", "label": "Natrium", "aliases": ("Natrium", "Na")},
    {"id": "kalium", "label": "Kalium", "aliases": ("Kalium", "K")},
    {"id": "crp", "label": "CRP", "aliases": ("CRP", "C-reaktives Protein", "C reaktives Protein")},
    {"id": "troponin_t", "label": "Troponin T", "aliases": ("Troponin T", "hs-Troponin T", "hs Troponin T", "TnT")},
    {"id": "bnp", "label": "BNP", "aliases": ("BNP", "B-Typ natriuretisches Peptid")},
    {"id": "albumin", "label": "Albumin", "aliases": ("Albumin",)},
    {"id": "other", "label": "Anderer Wert", "aliases": ()},
)

CATALOG_BY_ID = {item["id"]: item for item in LAB_CATALOG}
CATALOG_BY_LABEL = {item["label"]: item for item in LAB_CATALOG}


def normalize_label(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


_ALIAS_INDEX = tuple(
    (normalize_label(alias), item)
    for item in LAB_CATALOG
    for alias in item["aliases"]
    if normalize_label(alias)
)


def match_lab_label(text: str):
    """Only complete, explicitly registered aliases; never fuzzy/substring matches."""
    norm = normalize_label(text)
    return next((item for alias, item in _ALIAS_INDEX if alias == norm), None)


# Unit spelling is case-sensitive: g/l and G/l are different quantities.
IMPORT_UNITS = {
    "hb": ("g/l", "g/dl"),
    "leukozyten": ("G/l", "10^9/l"),
    "thrombozyten": ("G/l", "10^9/l"),
    "quick_inr": ("%", "INR", "1"),
    "ferritin": ("µg/l", "ng/ml"),
    "transferrinsaettigung": ("%",),
    "kreatinin": ("µmol/l", "mg/dl"),
    "natrium": ("mmol/l",),
    "kalium": ("mmol/l",),
    "crp": ("mg/l",),
    "troponin_t": ("ng/l", "pg/ml"),
    "bnp": ("ng/l", "pg/ml"),
    "albumin": ("g/l", "g/dl"),
}
IMPORTABLE_IDS = frozenset(IMPORT_UNITS)


def normalize_import_unit(raw: str, lab_id: str, *, ocr=False):
    """Normalize typography only. Never infer a missing unit or convert values."""
    unit = str(raw or "").strip().replace(" ", "").replace("μ", "µ")
    if ocr:
        # Verified slash/letter confusion in this template, preserving g/G case.
        unit = {"Gil": "G/l", "gil": "g/l"}.get(unit, unit)
    unit = unit.replace("/L", "/l").replace("/I", "/l")
    if unit.startswith("umol/") or unit.startswith("ug/"):
        unit = "µ" + unit[1:]
    return unit if unit in IMPORT_UNITS.get(lab_id, ()) else ""


def catalog_payload():
    return [{"id": item["id"], "label": item["label"], "aliases": list(item["aliases"])} for item in LAB_CATALOG]
