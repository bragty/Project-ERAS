from django.db.models import Q

from .models import TreatmentCase


def treatment_cases(*, query="", archived=False):
    qs = TreatmentCase.objects.select_related("patient", "checklist_state", "procedure_type").filter(archived=archived)
    query = (query or "").strip()
    if query:
        qs = qs.filter(
            Q(patient__name__icontains=query)
            | Q(patient__patient_number__icontains=query)
            | Q(case_number__icontains=query)
            | Q(procedure__icontains=query)
            | Q(procedure_type__name__icontains=query)
            | Q(surgeon__icontains=query)
            | Q(bene_nurse__icontains=query)
        )
    return qs.order_by("op_date", "case_number")


def treatment_case_by_number(case_number):
    return TreatmentCase.objects.select_related("patient", "checklist_state", "procedure_type").get(case_number=case_number)
