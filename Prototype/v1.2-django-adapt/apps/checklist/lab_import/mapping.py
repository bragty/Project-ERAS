"""Central mapping between KISIM/report labels and the checklist lab options.

The frontend stores the display label in ``STATE.labs[].type``. Display labels
are the exact KISIM names. Stable ``id`` values are used for the import
API/provenance and are mapped back to these labels.

``legacy`` entries are former options. They stay valid so stored rows keep
displaying, but they can be neither selected nor imported anymore.
"""
from __future__ import annotations

import re
import unicodedata

LAB_CATALOG = (
    {"id": "hb", "label": "Hämoglobin", "aliases": ("Hämoglobin", "Haemoglobin", "Hemoglobin", "Hb")},
    {"id": "haematokrit", "label": "Hämatokrit", "aliases": ("Hämatokrit", "Haematokrit", "Hämatocrit", "Hkt")},
    {"id": "thrombozyten", "label": "Thrombozyten", "aliases": ("Thrombozyten", "Thrombos", "Thrombo")},
    {"id": "leukozyten", "label": "Leukozyten", "aliases": ("Leukozyten", "Leukos", "Leuko")},
    {"id": "quick", "label": "Prothrombinzeit (Quick)", "aliases": ("Prothrombinzeit (Quick)", "Prothrombinzeit", "Quick")},
    {"id": "inr", "label": "INR", "aliases": ("INR",)},
    # OCR reads the KISIM "HbA1c" as "HbAlc" (verified on the supplied screenshot).
    {"id": "hba1c", "label": "HbA1c", "aliases": ("HbA1c", "Hb A1c", "HbAlc")},
    {"id": "kreatinin", "label": "Kreatinin", "aliases": ("Kreatinin", "Creatinin", "Creatinine")},
    {"id": "egfr", "label": "eGFR", "aliases": ("eGFR",)},
    {"id": "kalium", "label": "Kalium", "aliases": ("Kalium", "K")},
    {"id": "natrium", "label": "Natrium", "aliases": ("Natrium", "Na")},
    {
        "id": "troponin_t",
        "label": "Troponin-T high sensitive",
        "aliases": ("Troponin-T high sensitive", "Troponin T high sensitive", "Troponin T", "Troponin-T",
                    "hs-Troponin T", "hs Troponin T", "Troponin T hs", "TnT"),
    },
    {"id": "nt_probnp", "label": "NT-proBNP", "aliases": ("NT-proBNP", "NT-pro-BNP", "NTproBNP")},
    {"id": "asat", "label": "ASAT (GOT)", "aliases": ("ASAT (GOT)", "ASAT", "GOT")},
    {"id": "alat", "label": "ALAT (GPT)", "aliases": ("ALAT (GPT)", "ALAT", "GPT")},
    {"id": "ggt", "label": "Gamma-GT (GGT)", "aliases": ("Gamma-GT (GGT)", "Gamma-GT", "GGT")},
    {"id": "ap", "label": "Alkalische Phosphatase", "aliases": ("Alkalische Phosphatase", "AP")},
    {"id": "crp", "label": "CRP", "aliases": ("CRP", "C-reaktives Protein", "C reaktives Protein")},
    {
        "id": "transferrinsaettigung",
        "label": "Transferrinsättigung",
        "aliases": ("Transferrinsättigung", "Transferrinsaettigung", "Transferrin-Sättigung", "TSAT"),
    },
    {"id": "ferritin", "label": "Ferritin", "aliases": ("Ferritin",)},
    {"id": "vitamin_b12", "label": "Vitamin B12", "aliases": ("Vitamin B12", "Vit. B12", "Cobalamin")},
    {"id": "folsaeure", "label": "Folsäure", "aliases": ("Folsäure", "Folsaeure", "Folat")},
    {"id": "tsh", "label": "TSH", "aliases": ("TSH",)},
    {"id": "other", "label": "Anderer Wert", "aliases": ()},
    # Former options, kept only for rows that were stored before.
    {"id": "quick_inr", "label": "Quick / INR", "aliases": ("Quick / INR",), "legacy": True},
    {"id": "bnp", "label": "BNP", "aliases": ("BNP", "B-Typ natriuretisches Peptid"), "legacy": True},
    {"id": "albumin", "label": "Albumin", "aliases": ("Albumin",), "legacy": True},
)

CATALOG_BY_ID = {item["id"]: item for item in LAB_CATALOG}
CATALOG_BY_LABEL = {item["label"]: item for item in LAB_CATALOG}
SELECTABLE_LABELS = tuple(item["label"] for item in LAB_CATALOG if not item.get("legacy"))


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
    "haematokrit": ("l/l", "%"),
    "thrombozyten": ("G/l", "10^9/l"),
    "leukozyten": ("G/l", "10^9/l"),
    "quick": ("%",),
    # INR is a ratio; KISIM leaves its unit column empty.
    "inr": ("INR",),
    "hba1c": ("%", "mmol/mol"),
    "kreatinin": ("µmol/l", "mg/dl"),
    "egfr": ("ml/min/1.7m²", "ml/min/1.73m²"),
    "kalium": ("mmol/l",),
    "natrium": ("mmol/l",),
    "troponin_t": ("ng/l", "pg/ml"),
    "nt_probnp": ("ng/l", "pg/ml"),
    "asat": ("U/l", "µkat/l"),
    "alat": ("U/l", "µkat/l"),
    "ggt": ("U/l", "µkat/l"),
    "ap": ("U/l", "µkat/l"),
    "crp": ("mg/l",),
    "transferrinsaettigung": ("%",),
    "ferritin": ("µg/l", "ng/ml"),
    "vitamin_b12": ("pmol/l", "pg/ml", "ng/l"),
    "folsaeure": ("nmol/l", "µg/l", "ng/ml"),
    "tsh": ("mU/l", "mIU/l"),
    # Legacy entries: still validated for stored imported rows, never imported anew.
    "quick_inr": ("%", "INR", "1"),
    "bnp": ("ng/l", "pg/ml"),
    "albumin": ("g/l", "g/dl"),
}
IMPORTABLE_IDS = frozenset(item["id"] for item in LAB_CATALOG if item["id"] in IMPORT_UNITS and not item.get("legacy"))


def normalize_import_unit(raw: str, lab_id: str, *, ocr=False):
    """Normalize typography only. Never infer a missing unit or convert values."""
    unit = str(raw or "").strip().replace(" ", "").replace("μ", "µ")
    if lab_id == "inr" and unit in ("", "1", "INR"):
        return "INR"
    if ocr:
        # Verified slash/letter confusion in this template, preserving g/G case.
        unit = {"Gil": "G/l", "gil": "g/l", "I/l": "l/l", "Il": "l/l", "lil": "l/l", "IN": "l/l", "il": "l/l"}.get(unit, unit)
    unit = unit.replace("/L", "/l").replace("/I", "/l")
    if unit.startswith("umol/") or unit.startswith("ug/"):
        unit = "µ" + unit[1:]
    if unit.endswith("m2"):
        unit = unit[:-1] + "²"
    allowed = IMPORT_UNITS.get(lab_id, ())
    if unit in allowed:
        return unit
    return _ocr_unit_candidate(unit, allowed) if ocr and unit else ""


# OCR misreadings of the trailing "/l" observed on KISIM reports: the thin
# slash and l merge into N or A, or degrade to i, !, t or a lone slash.
_SLASH_L_TAILS = ("/l", "/!", "/t", "/i", "/1", "/|", "/", "il", "Il", "N", "A", "i", "I", "l", "!", "")


def _ocr_unit_candidate(unit, allowed):
    """Resolve known OCR glyph confusions, only if exactly one allowed unit fits.

    Nothing is added that is not visibly in the cell: a misread "/l" ending,
    a misread µ prefix (u, y, or p where pmol is no option), "mi/" for "ml/"
    and a misread superscript ² (?, *, 7). If the corrected reading fits
    several or no allowed units (e.g. g/l vs g/dl), the unit stays empty.
    """
    if unit.startswith("mi/"):
        unit = "ml/" + unit[3:]
    if unit.startswith("ml/min/") and unit[-1:] in "?*7" and unit[-2:-1] == "m":
        unit = unit[:-1] + "²"
    candidates = set()
    for tail in _SLASH_L_TAILS:
        if tail and not unit.endswith(tail):
            continue
        stem = unit[:len(unit)-len(tail)] if tail else unit
        if not stem:
            continue
        for prefix in ("", "u", "y", "p"):
            if prefix and not stem.startswith(prefix):
                continue
            fixed = ("µ" + stem[1:]) if prefix else stem
            if prefix == "p" and stem + "/l" in allowed:
                continue
            if any(u.startswith(fixed + "/") and u != fixed + "/l" for u in allowed):
                # e.g. Hb "g" + misread tail could be g/l or g/dl: never guess.
                return ""
            if fixed + "/l" in allowed:
                candidates.add(fixed + "/l")
    if unit in allowed:
        candidates.add(unit)
    return next(iter(candidates)) if len(candidates) == 1 else ""


# Stored labels of former versions that map unambiguously to a current label.
_RENAMED_LABELS = {"Hb": "Hämoglobin", "Troponin T": "Troponin-T high sensitive"}


def migrate_lab_row(row):
    """Rename a stored lab row to the current KISIM label. Idempotent.

    "Quick / INR" is split only when the stored unit or the imported source
    label decides unambiguously between Quick and INR; otherwise it stays a
    legacy row. BNP and Albumin are different analytes and are never renamed.
    """
    if not isinstance(row, dict) or not isinstance(row.get("type"), str):
        return row
    label = row.get("type")
    meta = row.get("importMeta") if isinstance(row.get("importMeta"), dict) else None
    target = _RENAMED_LABELS.get(label)
    if label == "Quick / INR":
        source = match_lab_label(meta.get("originalLabel")) if meta else None
        unit = str(row.get("unit") or "").strip()
        if source and source["id"] in ("quick", "inr"):
            target = source["label"]
        elif unit == "%":
            target = "Prothrombinzeit (Quick)"
        elif unit in ("INR", "1"):
            target = "INR"
    if not target:
        return row
    row = {**row, "type": target}
    if meta:
        row["importMeta"] = {**meta, "labId": CATALOG_BY_LABEL[target]["id"]}
    if target == "INR" and str(row.get("unit") or "").strip() == "1":
        row["unit"] = "INR"
    return row


def migrate_lab_rows(rows):
    return [migrate_lab_row(row) for row in rows] if isinstance(rows, list) else rows


def catalog_payload():
    return [{"id": item["id"], "label": item["label"], "aliases": list(item["aliases"]),
             "legacy": bool(item.get("legacy"))} for item in LAB_CATALOG]
