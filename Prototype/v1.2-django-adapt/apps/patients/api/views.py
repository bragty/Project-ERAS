from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.http import require_http_methods

from apps.core.api import ApiError, error_response, ok, parse_json_body

from ..selectors import treatment_case_by_number, treatment_cases
from ..serializers import case_to_dict
from ..services import create_patient_case


def _parse_archived(value):
    return str(value or "false").lower() in {"1", "true", "yes", "ja"}


@require_http_methods(["GET", "POST"])
def patients_collection(request):
    try:
        if request.method == "GET":
            cases = treatment_cases(
                query=request.GET.get("q", ""),
                archived=_parse_archived(request.GET.get("archived")),
            )
            return ok({"results": [case_to_dict(case) for case in cases]})

        case = create_patient_case(parse_json_body(request))
        case = treatment_case_by_number(case.case_number)
        return ok({"case": case_to_dict(case)}, status=201)
    except ApiError as exc:
        return error_response(exc)


@require_http_methods(["GET"])
def case_detail(request, case_number):
    try:
        case = treatment_case_by_number(case_number)
    except ObjectDoesNotExist:
        return error_response(ApiError("Fall nicht gefunden.", status=404, code="case_not_found"))
    return ok({"case": case_to_dict(case)})
