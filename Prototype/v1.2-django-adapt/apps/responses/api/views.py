from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.http import require_http_methods

from apps.core.api import ApiError, error_response, ok, parse_json_body
from apps.patients.selectors import treatment_case_by_number

from ..serializers import checklist_state_to_dict
from ..services import get_state, reset_state, save_state


def _case_or_404(case_number):
    try:
        return treatment_case_by_number(case_number)
    except ObjectDoesNotExist as exc:
        raise ApiError("Fall nicht gefunden.", status=404, code="case_not_found") from exc



@require_http_methods(["GET", "PUT", "DELETE"])
def case_state(request, case_number):
    try:
        treatment_case = _case_or_404(case_number)
        if request.method == "GET":
            return ok(checklist_state_to_dict(*get_state(treatment_case)))
        if request.method == "DELETE":
            return ok(checklist_state_to_dict(*reset_state(treatment_case)))

        body = parse_json_body(request)
        raw_state = body.get("state", body)
        if not isinstance(raw_state, dict):
            raise ApiError("state muss ein JSON-Objekt sein.", code="validation_error")
        return ok(checklist_state_to_dict(*save_state(treatment_case, raw_state)))
    except ApiError as exc:
        return error_response(exc)
