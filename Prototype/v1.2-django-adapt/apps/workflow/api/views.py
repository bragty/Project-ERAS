from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.http import require_POST

from apps.core.api import ApiError, error_response, ok
from apps.patients.selectors import treatment_case_by_number
from apps.patients.serializers import case_to_dict

from ..services import archive_case, restore_case


def _case(case_number):
    try:
        return treatment_case_by_number(case_number)
    except ObjectDoesNotExist as exc:
        raise ApiError("Fall nicht gefunden.", status=404, code="case_not_found") from exc


@require_POST
def archive(request, case_number):
    try:
        case = archive_case(_case(case_number))
        case = treatment_case_by_number(case.case_number)
        return ok({"case": case_to_dict(case)})
    except ApiError as exc:
        return error_response(exc)


@require_POST
def restore(request, case_number):
    try:
        case = restore_case(_case(case_number))
        case = treatment_case_by_number(case.case_number)
        return ok({"case": case_to_dict(case)})
    except ApiError as exc:
        return error_response(exc)
