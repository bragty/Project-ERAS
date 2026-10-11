from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.http import require_GET, require_POST

from apps.core.api import ApiError, error_response, ok
from apps.patients.selectors import treatment_case_by_number

from ..lab_import.mapping import catalog_payload
from ..lab_import.service import process_lab_upload
from ..schema import ALL_ITEM_IDS, CURRENT_SCHEMA_VERSION, FIELD_RULES, PATH_ITEM_IDS, PREOP_ITEM_IDS


@require_GET
def schema_info(request):
    return ok(
        {
            "schemaVersion": CURRENT_SCHEMA_VERSION,
            "counts": {
                "preop": len(PREOP_ITEM_IDS),
                "path": len(PATH_ITEM_IDS),
                "total": len(ALL_ITEM_IDS),
            },
            "fieldRules": FIELD_RULES,
            "labCatalog": catalog_payload(),
        }
    )


@require_POST
def lab_import(request, case_number):
    """Extract laboratory values into a preview; never saves them directly."""
    try:
        try:
            treatment_case = treatment_case_by_number(case_number)
        except ObjectDoesNotExist as exc:
            raise ApiError("Fall nicht gefunden.", status=404, code="case_not_found") from exc

        upload = request.FILES.get("file")
        if upload is None:
            raise ApiError("Keine Datei übermittelt.", code="lab_import_missing_file")
        return ok(process_lab_upload(upload, treatment_case))
    except ApiError as exc:
        return error_response(exc)
