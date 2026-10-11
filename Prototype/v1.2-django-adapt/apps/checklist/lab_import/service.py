from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import tempfile
import time

from django.conf import settings

from apps.audit.services import record_event
from apps.core.api import ApiError
from apps.responses.services import get_state

from .parser import Word, parse_positioned_words, report_identity


def _words_text(words):
    from .parser import _group_lines, _text
    from statistics import median
    if not words:
        return ""
    height = median(w.y1-w.y0 for w in words)
    return "\n".join(_text(line) for line in _group_lines(words, max(1, height*.7)))


def _sniff(data: bytes):
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    return None


def _validate_upload(upload):
    max_bytes = int(getattr(settings, "LAB_IMPORT_MAX_BYTES", 10 * 1024 * 1024))
    if upload.size > max_bytes:
        raise ApiError(
            f"Datei ist zu gross. Maximal {max_bytes // (1024 * 1024)} MB erlaubt.",
            status=413,
            code="lab_import_file_too_large",
        )
    data = upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ApiError("Datei ist zu gross.", status=413, code="lab_import_file_too_large")
    kind = _sniff(data)
    if not kind:
        raise ApiError("Nur PDF, PNG und JPEG werden unterstützt.", code="lab_import_unsupported_file")
    suffix = Path(upload.name or "").suffix.lower()
    allowed_suffixes = {"pdf": {".pdf"}, "png": {".png"}, "jpeg": {".jpg", ".jpeg"}}
    if suffix and suffix not in allowed_suffixes[kind]:
        raise ApiError("Dateiendung und Dateiinhalt stimmen nicht überein.", code="lab_import_file_mismatch")
    return data, kind


def _pdf_words(page):
    return [
        Word(
            text=str(item.get("text") or ""),
            x0=float(item.get("x0") or 0),
            y0=float(item.get("top") or 0),
            x1=float(item.get("x1") or 0),
            y1=float(item.get("bottom") or 0),
            confidence=100.0,
        )
        for item in page.extract_words(x_tolerance=2, y_tolerance=3, keep_blank_chars=False)
        if str(item.get("text") or "").strip()
    ]


def _prepare_image(image):
    from PIL import ImageOps, ImageEnhance

    image = ImageOps.exif_transpose(image).convert("RGB")
    max_pixels = int(getattr(settings, "LAB_IMPORT_MAX_IMAGE_PIXELS", 25_000_000))
    if image.width * image.height > max_pixels:
        raise ApiError("Bildauflösung ist zu gross.", code="lab_import_image_too_large")
    # The KISIM table uses small fonts. Upscaling before OCR materially improves
    # recognition while remaining below the configured pixel budget.
    target_width = min(2600, max(image.width, 2600))
    if image.width < target_width:
        factor = target_width / image.width
        target_size = (int(image.width * factor), int(image.height * factor))
        if target_size[0] * target_size[1] <= max_pixels:
            image = image.resize(target_size)
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    gray = ImageEnhance.Sharpness(gray).enhance(1.2)
    return gray


def _ocr_words(image):
    import pytesseract
    from pytesseract import Output

    timeout = int(getattr(settings, "LAB_IMPORT_OCR_TIMEOUT_SECONDS", 30))
    deadline = time.monotonic() + timeout
    try:
        osd = pytesseract.image_to_osd(image, output_type=Output.DICT, timeout=min(timeout, 10))
        rotate = int(osd.get("rotate") or 0)
        if rotate:
            image = image.rotate(-rotate, expand=True)
    except Exception:
        # OSD may fail on sparse pages; extraction can still continue.
        pass

    try:
        frame = pytesseract.image_to_data(
            image,
            lang=getattr(settings, "LAB_IMPORT_OCR_LANG", "deu+eng"),
            config="--psm 6",
            output_type=Output.DICT,
            timeout=max(.1, deadline-time.monotonic()),
        )
    except pytesseract.TesseractNotFoundError as exc:
        raise ApiError("OCR ist auf dem Server nicht installiert (Tesseract fehlt).", status=503, code="lab_import_ocr_unavailable") from exc
    except RuntimeError as exc:
        raise ApiError("OCR-Verarbeitung hat das Zeitlimit überschritten oder ist fehlgeschlagen.", status=422, code="lab_import_ocr_failed") from exc
    words = []
    for index in range(len(frame["text"])):
        row = {key: values[index] for key, values in frame.items()}
        text = str(row.get("text") or "").strip()
        try:
            conf = float(row.get("conf") or -1)
        except (TypeError, ValueError):
            conf = -1
        if not text or conf < 0:
            continue
        left = float(row.get("left") or 0)
        top = float(row.get("top") or 0)
        width = float(row.get("width") or 0)
        height = float(row.get("height") or 0)
        words.append(Word(text, left, top, left + width, top + height, conf))
    words = _refine_unit_cells(image, words, deadline)
    return image, words


def _refine_unit_cells(image, words, deadline):
    """Re-read only ambiguous unit cells, never infer units from expected values."""
    from statistics import median
    import pytesseract
    from .mapping import match_lab_label, normalize_label, normalize_import_unit
    from .parser import _group_lines, _text
    if not words:
        return words
    height = median(w.y1-w.y0 for w in words)
    lines = _group_lines(words, max(1, height*.7))
    names = ("untersuchungen", "flag", "resultat", "einheit", "referenzbereich")
    headers = []
    for line in lines:
        mapping = {normalize_label(w.text): w for w in line}
        if all(name in mapping for name in names):
            anchors = [mapping[name] for name in names]
            if all(a.x1 < b.x0 for a, b in zip(anchors, anchors[1:])):
                headers.append(anchors)
    if len(headers) != 1:
        return words
    label_h, flag_h, result_h, unit_h, ref_h = headers[0]
    refined = list(words)
    for line in lines:
        if min(w.cy for w in line) <= max(w.y1 for w in headers[0]):
            continue
        label = _text([w for w in line if label_h.x0-height <= w.x0 < flag_h.x0-height*.2])
        lab = match_lab_label(label)
        if not lab:
            continue
        cells = [w for w in line if unit_h.x0-height*.2 <= w.cx < ref_h.x0-height*.2]
        if normalize_import_unit(_text(cells), lab["id"], ocr=True):
            continue
        if time.monotonic() >= deadline:
            break
        cy = median(w.cy for w in line)
        box = (max(0, int(unit_h.x0-height*.5)), max(0, int(cy-height*.85)),
               min(image.width, int(ref_h.x0-height*.5)), min(image.height, int(cy+height*.85)))
        crop = image.crop(box)
        crop = crop.resize((crop.width*3, crop.height*3))
        try:
            data = pytesseract.image_to_data(crop, lang=getattr(settings, "LAB_IMPORT_OCR_LANG", "deu+eng"),
                config="--psm 7", output_type=pytesseract.Output.DICT,
                timeout=max(.1, deadline-time.monotonic()))
        except RuntimeError:
            continue
        tokens = [(str(t).strip(), float(c)) for t, c in zip(data["text"], data["conf"]) if str(t).strip() and float(c) >= 0]
        raw = " ".join(t for t, _ in tokens)
        # If the focused reading is still unclear, retain the original for review.
        if tokens and normalize_import_unit(raw, lab["id"], ocr=True):
            refined = [w for w in refined if w not in cells]
            refined.append(Word(raw, unit_h.x0, cy-height/2, min(ref_h.x0-height, unit_h.x0+len(raw)*height*.6), cy+height/2, min(c for _, c in tokens)))
    return refined


def _render_pdf_page(pdf_path, index):
    import pypdfium2 as pdfium
    from PIL import Image

    document = pdfium.PdfDocument(str(pdf_path))
    try:
        page = document[index]
        try:
            if page.get_width()*page.get_height()*4 > int(getattr(settings, "LAB_IMPORT_MAX_IMAGE_PIXELS", 25_000_000)):
                raise ApiError("PDF-Seitenauflösung ist zu gross.", code="lab_import_image_too_large")
            bitmap = page.render(scale=2.0)
            try:
                return bitmap.to_pil().convert("RGB")
            finally:
                bitmap.close()
        finally:
            page.close()
    finally:
        document.close()


def _process_pdf(data: bytes):
    import pdfplumber

    max_pages = int(getattr(settings, "LAB_IMPORT_MAX_PAGES", 10))
    all_suggestions = []
    all_times = []
    warnings = []
    full_text_parts = []
    used_methods = set()

    with tempfile.NamedTemporaryFile(prefix="eras-lab-", suffix=".pdf", delete=False) as handle:
        handle.write(data)
        path = Path(handle.name)
    try:
        try:
            pdf = pdfplumber.open(str(path))
        except Exception as exc:
            raise ApiError("PDF kann nicht gelesen werden (beschädigt oder verschlüsselt).", code="lab_import_invalid_pdf") from exc
        with pdf:
            if len(pdf.pages) > max_pages:
                raise ApiError(f"PDF enthält zu viele Seiten (maximal {max_pages}).", code="lab_import_too_many_pages")
            for index, page in enumerate(pdf.pages):
                page_no = index + 1
                page_text = page.extract_text() or ""
                full_text_parts.append(page_text)
                direct = parse_positioned_words(_pdf_words(page), page=page_no, width=float(page.width), method="pdf_text")
                page_suggestions = direct["suggestions"]
                page_times = direct["measurementTimes"]
                page_warnings = direct["warnings"]
                if direct["layoutRecognized"]:
                    used_methods.add("pdf_text")
                else:
                    # If a PDF is a scan or the text layer does not preserve the
                    # table, render that page and run OCR only for this page.
                    image = _prepare_image(_render_pdf_page(path, index))
                    image, words = _ocr_words(image)
                    ocr = parse_positioned_words(words, page=page_no, width=float(image.width), method="ocr")
                    page_suggestions = ocr["suggestions"]
                    page_times = ocr["measurementTimes"]
                    page_warnings = ocr["warnings"]
                    if page_suggestions:
                        used_methods.add("ocr")
                    full_text_parts.append(_words_text(words))
                all_suggestions.extend(page_suggestions)
                all_times.extend(page_times)
                warnings.extend(page_warnings)
        return all_suggestions, sorted(set(all_times), reverse=True), warnings, "\n".join(full_text_parts), sorted(used_methods)
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


def _process_image(data: bytes):
    from PIL import Image, UnidentifiedImageError

    try:
        image = Image.open(io.BytesIO(data))
    except (UnidentifiedImageError, OSError) as exc:
        raise ApiError("Bilddatei kann nicht gelesen werden.", code="lab_import_invalid_image") from exc
    image = _prepare_image(image)
    image, words = _ocr_words(image)
    parsed = parse_positioned_words(words, page=1, width=float(image.width), method="ocr")
    full_text = _words_text(words)
    return parsed["suggestions"], parsed["measurementTimes"], parsed["warnings"], full_text, ["ocr"] if parsed["suggestions"] else []


def _patient_match(identity, treatment_case):
    checks = []
    if identity.get("caseNumber"):
        checks.append(("caseNumber", identity["caseNumber"], treatment_case.case_number))
    if identity.get("patientNumber") and treatment_case.patient.patient_number:
        checks.append(("patientNumber", identity["patientNumber"], treatment_case.patient.patient_number))
    if not checks:
        return {
            "status": "unverified",
            "message": "Im Bericht wurde keine eindeutige Patienten- oder Fallkennung sicher erkannt. Bitte Zuordnung manuell prüfen.",
        }
    mismatches = [key for key, report_value, current_value in checks if str(report_value).casefold() != str(current_value).casefold()]
    if mismatches:
        return {
            "status": "mismatch",
            "message": "Die eindeutige Kennung im Bericht stimmt nicht mit dem geöffneten Fall überein.",
            "mismatchedFields": mismatches,
        }
    return {"status": "match", "message": "Erkannte eindeutige Kennung stimmt mit dem geöffneten Fall überein."}


def _apply_existing_conflicts(suggestions, treatment_case):
    _obj, state, _summary, _derived, _errors = get_state(treatment_case)
    existing = state.get("labs") or []
    by_label = {}
    for index, row in enumerate(existing):
        if not str(row.get("type") or "").strip() or not str(row.get("value") or "").strip():
            continue
        by_label.setdefault(row.get("type"), []).append((index, row))
    for suggestion in suggestions:
        matches = by_label.get(suggestion["labLabel"], [])
        duplicate = next(
            (
                row
                for _index, row in matches
                if (row.get("importMeta") or {}).get("sourceHash") == suggestion.get("sourceHash")
                and (row.get("importMeta") or {}).get("labId") == suggestion["labId"]
                and (row.get("importMeta") or {}).get("measurementAt") == suggestion.get("measurementAt")
            ),
            None,
        )
        suggestion["alreadyImported"] = bool(duplicate)
        if matches:
            suggestion["existingConflicts"] = [
                {
                    "rowIndex": index,
                    "value": str(row.get("value") or ""),
                    "unit": str(row.get("unit") or ""),
                    "measurementAt": (row.get("importMeta") or {}).get("measurementAt"),
                }
                for index, row in matches
            ]
            suggestion["status"] = "review"
            suggestion["warnings"].append("Für diesen Laborparameter ist bereits ein Wert vorhanden. Übernahme muss bewusst bestätigt werden.")
        else:
            suggestion["existingConflicts"] = []


def process_lab_upload(upload, treatment_case):
    data, kind = _validate_upload(upload)
    digest = hashlib.sha256(data).hexdigest()
    if kind == "pdf":
        suggestions, times, warnings, full_text, methods = _process_pdf(data)
    else:
        suggestions, times, warnings, full_text, methods = _process_image(data)

    identity = report_identity(full_text)
    patient_match = _patient_match(identity, treatment_case)
    for suggestion in suggestions:
        suggestion["sourceHash"] = digest
    _apply_existing_conflicts(suggestions, treatment_case)
    for suggestion in suggestions:
        if suggestion.get("alreadyImported"):
            suggestion["status"] = "review"
            suggestion["warnings"].append("Dieser Wert aus demselben Bericht wurde bereits übernommen.")

    if not suggestions:
        warnings.append("Keine unterstützten Laborwerte konnten sicher erkannt werden. Bericht bitte manuell erfassen oder Layout-Konfiguration ergänzen.")

    record_event(
        event_type="lab_import_processed",
        treatment_case=treatment_case,
        entity_type="LabImport",
        entity_id=digest[:16],
        metadata={
            "fileType": kind,
            "suggestionCount": len(suggestions),
            "measurementTimeCount": len(times),
            "methods": methods,
            "patientMatch": patient_match["status"],
        },
    )

    return {
        "sourceHash": digest,
        "fileName": Path(upload.name or "Laborbericht").name,
        "fileType": kind,
        "measurementTimes": times,
        "patientMatch": patient_match,
        "blocked": patient_match["status"] == "mismatch",
        "suggestions": suggestions,
        "warnings": list(dict.fromkeys(warnings)),
        "extractionMethods": methods,
    }
