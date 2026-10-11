"""Server-side allowlist for confirmed import rows; manual rows stay unchanged."""
from apps.core.api import ApiError
from .mapping import CATALOG_BY_ID, IMPORTABLE_IDS, normalize_import_unit, match_lab_label
from .parser import normalize_numeric


def validate_imported_labs(rows):
    for row in rows:
        if not isinstance(row, dict):
            continue
        meta = row.get("importMeta")
        if not meta:
            continue
        if not isinstance(meta, dict):
            raise ApiError("Ungültige Laborimport-Angaben.", status=422, code="invalid_lab_import")
        lab_id = meta.get("labId")
        lab = CATALOG_BY_ID.get(lab_id) if isinstance(lab_id, str) else None
        if not lab or lab_id not in IMPORTABLE_IDS or row.get("type") != lab["label"]:
            raise ApiError("Importierter Laborparameter ist nicht auswählbar oder falsch zugeordnet.", status=422, code="invalid_lab_import")
        if meta.get("templateId") == "kisim-single-result-v1":
            source_lab = match_lab_label(meta.get("originalLabel"))
            if not source_lab or source_lab["id"] != lab_id:
                raise ApiError("Laborparameter stimmt nicht mit der erkannten Untersuchung überein.", status=422, code="invalid_lab_import")
        if normalize_numeric(row.get("value"))[1] is None:
            raise ApiError("Importierter Laborwert ist kein gültiger Zahlenwert.", status=422, code="invalid_lab_import")
        if not normalize_import_unit(row.get("unit"), lab_id):
            raise ApiError("Einheit des importierten Laborwerts bitte kontrollieren.", status=422, code="invalid_lab_import")
