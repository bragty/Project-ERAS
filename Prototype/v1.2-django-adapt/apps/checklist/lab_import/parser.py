"""Strict parser for the supplied KISIM single-result report (Beispiel Labor).

Coordinates are normalized to page width. Only the five verified table headers
are accepted. Sample dates/times are intentionally not read or stored.
"""
from __future__ import annotations
from dataclasses import dataclass
from statistics import median
import re
from .mapping import IMPORTABLE_IDS, match_lab_label, normalize_label, normalize_import_unit

TEMPLATE_ID = "kisim-single-result-v1"
VALUE_RE = re.compile(r"^\s*(?P<op>[<>]=?)?\s*(?P<num>[+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+))\s*(?P<flag>\*)?\s*$")

@dataclass(frozen=True)
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    confidence: float = 100.0

    @property
    def cx(self):
        return (self.x0 + self.x1) / 2

    @property
    def cy(self):
        return (self.y0 + self.y1) / 2


def normalize_numeric(raw: str):
    """Return (operator, normalized-number-string) without losing < or >."""
    raw = str(raw or "").strip().replace("−", "-").replace("–", "-")
    # KISIM marks abnormal values next to the number. OCR may read that marker
    # as *, °, quotes or guillemets; these suffixes are not part of the value.
    raw = re.sub(r"[\s*°\"'»«]+$", "", raw).strip()
    # KISIM appends footnote references to some results, e.g. "92 (1)".
    raw = re.sub(r"\s*\(\d{1,2}\)$", "", raw).strip()
    match = VALUE_RE.match(raw)
    if not match:
        return None, None
    operator = match.group("op") or ""
    number = match.group("num").replace(",", ".")
    if number.startswith("."):
        number = "0" + number
    if number.startswith("-."):
        number = "-0" + number[1:]
    return operator, number


def _group_lines(words, tolerance):
    groups = []
    for word in sorted(words, key=lambda w: (w.cy, w.x0)):
        if groups and abs(word.cy - median(w.cy for w in groups[-1])) <= tolerance:
            groups[-1].append(word)
        else:
            groups.append([word])
    return [sorted(line, key=lambda w: w.x0) for line in groups]


def _text(words):
    return " ".join(w.text.strip() for w in words).strip()


def parse_positioned_words(words: list[Word], *, page: int, width: float, method: str):
    empty = {"suggestions": [], "warnings": [],
             "layoutRecognized": False, "templateId": TEMPLATE_ID}
    if width <= 0 or not words:
        empty["warnings"] = [f"Seite {page}: keine lesbare KISIM-Tabelle erkannt."]
        return empty
    scale = 1000 / width
    words = [Word(w.text, w.x0*scale, w.y0*scale, w.x1*scale, w.y1*scale, w.confidence)
             for w in words if w.text.strip()]
    height = median(w.y1-w.y0 for w in words)
    lines = _group_lines(words, max(1, height * .7))
    names = ("untersuchungen", "flag", "resultat", "einheit", "referenzbereich")
    headers = []
    for line in lines:
        by_name = {normalize_label(w.text): w for w in line}
        if all(name in by_name for name in names):
            anchors = [by_name[name] for name in names]
            if all(a.x1 < b.x0 for a, b in zip(anchors, anchors[1:])):
                headers.append(anchors)
    if len(headers) != 1:
        empty["warnings"] = [f"Seite {page}: erwartetes KISIM-Format mit Untersuchungen, Flag, Resultat, Einheit und Referenzbereich nicht eindeutig erkannt. Keine Werte übernommen."]
        return empty
    label_h, flag_h, result_h, unit_h, reference_h = headers[0]
    table_y = max(w.y1 for w in headers[0])
    warnings = []
    # Boundaries are anchored to the actual headings, not hard-coded row numbers.
    label_right = flag_h.x0 - height*.2
    result_left = (flag_h.x1 + result_h.x0)/2
    unit_left = unit_h.x0 - height*.2
    reference_left = reference_h.x0 - height*.2
    suggestions = []
    ignored = 0
    for line in lines:
        if min(w.cy for w in line) <= table_y:
            continue
        label_words = [w for w in line if label_h.x0-height <= w.x0 < label_right]
        label = _text(label_words)
        lab = match_lab_label(label)
        result_words = [w for w in line if result_left <= w.cx < unit_left]
        if not lab or lab["id"] not in IMPORTABLE_IDS:
            if label and result_words:
                ignored += 1
            continue
        unit_words = [w for w in line if unit_left <= w.cx < reference_left]
        raw_value = _text(result_words)
        operator, value = normalize_numeric(raw_value)
        # Missing/ambiguous cells stay blank, never borrow reference values.
        raw_unit = _text(unit_words)
        unit = normalize_import_unit(raw_unit, lab["id"], ocr=method == "ocr")
        item_warnings = []
        if value is None:
            item_warnings.append("Resultat fehlt oder ist nicht eindeutig lesbar; manuell prüfen.")
        if not unit:
            item_warnings.append("Einheit fehlt oder passt nicht eindeutig zum Laborparameter; manuell prüfen.")
        confidence = min((w.confidence for w in label_words+result_words+unit_words), default=0)
        if method == "ocr":
            # Every OCR proposal requires conscious selection, even high scores.
            item_warnings.append("Aus einem Bild erkannt: Wert und Einheit vor der Übernahme kontrollieren.")
            if confidence < 70:
                item_warnings.append("Niedrige OCR-Sicherheit.")
        suggestions.append({
            "labId": lab["id"], "labLabel": lab["label"], "originalLabel": label,
            "originalValue": raw_value, "normalizedValue": value or "",
            "comparisonOperator": operator or "", "originalUnit": raw_unit,
            "normalizedUnit": unit, "sourcePage": page,
            "sourceExcerpt": _text(line), "extractionMethod": method,
            "confidence": round(confidence, 1), "status": "review" if item_warnings else "ready",
            "warnings": item_warnings, "templateId": TEMPLATE_ID,
        })
    if ignored:
        warnings.append(f"{ignored} Untersuchungen ausserhalb der auswählbaren Laborwerte wurden ignoriert.")
    return {"suggestions": suggestions, "warnings": warnings, "layoutRecognized": True, "templateId": TEMPLATE_ID}


def report_identity(text: str):
    """Extract only explicit identifiers. A name alone is intentionally ignored."""
    text = str(text or "")
    patterns = {
        "patientNumber": (
            r"(?:Patient(?:en)?[-\s]*(?:Nr|Nummer)|Pat\.?[-\s]*Nr)\s*[:#]?\s*([A-Za-z0-9._/-]{3,})",
        ),
        "caseNumber": (
            r"(?:Fall[-\s]*(?:Nr|Nummer)|Fallnummer)\s*[:#]?\s*([A-Za-z0-9._/-]{3,})",
        ),
    }
    found = {}
    for key, regexes in patterns.items():
        for regex in regexes:
            match = re.search(regex, text, flags=re.IGNORECASE)
            if match:
                found[key] = match.group(1)
                break
    return found
