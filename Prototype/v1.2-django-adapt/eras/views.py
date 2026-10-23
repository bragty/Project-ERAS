from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie

from apps.checklist.models import ProcedureType
from apps.checklist.services import effective_definition
from apps.patients.models import TreatmentCase


@ensure_csrf_cookie
def home(request):
    return render(
        request,
        "eras/pages/home.html",
        {
            "page_title": "BENE Plattform - Frontpage V1.1",
            "procedure_types": ProcedureType.objects.filter(active=True),
        },
    )


@ensure_csrf_cookie
def checklist(request):
    # Every persisted checklist belongs to a treatment case. A free-floating
    # checklist is intentionally not supported by the backend architecture.
    case_number = request.GET.get("case")
    if not case_number:
        return redirect("eras:home")
    # The case's Eingriffsart decides which items are shown.
    treatment_case = TreatmentCase.objects.select_related("procedure_type").filter(case_number=case_number).first()
    return render(
        request,
        "eras/pages/checklist.html",
        {"page_title": "BENE Plattform", "checklist_definition": effective_definition(treatment_case)},
    )
