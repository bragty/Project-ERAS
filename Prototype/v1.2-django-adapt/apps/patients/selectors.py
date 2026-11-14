from django.db.models import F, Q, Value, IntegerField
from django.db.models.functions import Coalesce, Lower, NullIf, Trim

from apps.core.api import ApiError

from .models import TreatmentCase


CASE_SORTS = {
    "op_asc": F("op_date").asc(nulls_last=True),
    "op_desc": F("op_date").desc(nulls_last=True),
    "progress_asc": F("_progress").asc(),
    "progress_desc": F("_progress").desc(),
    "patient_asc": Lower("patient__patient_number").asc(nulls_last=True),
    "patient_desc": Lower("patient__patient_number").desc(nulls_last=True),
    # Cases without a surgeon stay at the end in both directions.
    "surgeon_asc": F("_surgeon").asc(nulls_last=True),
    "surgeon_desc": F("_surgeon").desc(nulls_last=True),
    "updated_desc": F("updated_at").desc(),
}


def case_query_options(params):
    from .services import _parse_iso_date
    result = {"sort": params.get("sort", "op_asc"), "op_status": params.get("opStatus", "all"),
              "progress_status": params.get("progressStatus", "all"),
              "surgeon": str(params.get("surgeon", "")).strip()}
    errors = {}
    for key, choices in (("sort", CASE_SORTS), ("op_status", ("all", "dated", "missing")),
                         ("progress_status", ("all", "open", "complete", "not_started"))):
        if result[key] not in choices:
            errors[key] = "Ungültige Auswahl."
    for query_key, key in (("opFrom", "op_from"), ("opTo", "op_to")):
        try:
            result[key] = _parse_iso_date(params.get(query_key), query_key)
        except ApiError as exc:
            errors.update(exc.fields)
    if len(result["surgeon"]) > 255:
        errors["surgeon"] = "Ungültige Auswahl."
    if result.get("op_from") and result.get("op_to") and result["op_from"] > result["op_to"]:
        errors["opTo"] = "Das Enddatum muss am oder nach dem Startdatum liegen."
    if errors:
        raise ApiError("Bitte die Filter prüfen.", status=422, code="validation_error", fields=errors)
    return result


# Filter value for cases without a recorded surgeon.
NO_SURGEON = "__none__"


def treatment_cases(*, query="", archived=False, sort="op_asc", op_status="all", progress_status="all", op_from=None, op_to=None,
                    surgeon=""):
    qs = TreatmentCase.objects.select_related("patient", "checklist_state", "procedure_type").filter(archived=archived)
    query = (query or "").strip()
    if query:
        qs = qs.filter(
            Q(patient__patient_number__icontains=query)
            | Q(procedure__icontains=query)
            | Q(procedure_type__name__icontains=query)
            | Q(surgeon__icontains=query)
            | Q(bene_nurse__icontains=query)
        )
    qs = qs.annotate(_progress=Coalesce("checklist_state__progress_total", Value(0), output_field=IntegerField()),
                     _surgeon=NullIf(Lower(Trim("surgeon")), Value("")))
    if surgeon == NO_SURGEON:
        qs = qs.filter(_surgeon__isnull=True)
    elif surgeon:
        # Compare in Python: SQLite's LOWER() ignores umlauts (e.g. "Ö").
        wanted = surgeon.casefold()
        spellings = {name for name in TreatmentCase.objects.exclude(surgeon="").values_list("surgeon", flat=True)
                     if name.strip().casefold() == wanted}
        qs = qs.filter(surgeon__in=spellings)
    if op_status == "missing":
        qs = qs.filter(op_date__isnull=True)
    elif op_status == "dated":
        qs = qs.filter(op_date__isnull=False)
    if op_from:
        qs = qs.filter(op_date__gte=op_from)
    if op_to:
        qs = qs.filter(op_date__lte=op_to)
    if progress_status == "complete":
        qs = qs.filter(checklist_state__complete=True)
    elif progress_status == "open":
        qs = qs.filter(Q(checklist_state__complete=False) | Q(checklist_state__isnull=True))
    elif progress_status == "not_started":
        qs = qs.filter(_progress=0)
    return qs.order_by(CASE_SORTS[sort], "case_number")


def surgeon_options(*, archived=False):
    """Distinct surgeons of the active or archived cases, for the filter list."""
    names = {}
    for name in TreatmentCase.objects.filter(archived=archived).exclude(surgeon="").order_by("created_at").values_list("surgeon", flat=True):
        names.setdefault(name.strip().casefold(), name.strip())
    return sorted((name for key, name in names.items() if key), key=str.casefold)


def treatment_case_by_number(case_number):
    return TreatmentCase.objects.select_related("patient", "checklist_state", "procedure_type").get(case_number=case_number)
