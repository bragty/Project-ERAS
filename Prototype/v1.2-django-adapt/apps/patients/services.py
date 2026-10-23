from datetime import date

from django.db import IntegrityError, transaction

from apps.audit.services import record_event
from apps.checklist.models import ProcedureType
from apps.core.api import ApiError
from apps.responses.services import create_initial_checklist_state

from .models import Patient, TreatmentCase


def _clean_text(value):
    return str(value or "").strip()


def _parse_iso_date(value, field_name="opDate"):
    value = _clean_text(value)
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ApiError(
            "Ungültiges Datum. Erwartet wird YYYY-MM-DD.",
            code="validation_error",
            fields={field_name: "Ungültiges Datum."},
        ) from exc


def _procedure_type(payload):
    """Eingriffsart from ``procedureTypeId`` or, for older clients, by the name
    sent as ``procedure``. No type means the full checklist."""
    type_id = payload.get("procedureTypeId")
    if type_id not in (None, ""):
        try:
            return ProcedureType.objects.get(pk=int(type_id))
        except (TypeError, ValueError, ProcedureType.DoesNotExist) as exc:
            raise ApiError(
                "Unbekannte Eingriffsart.",
                code="validation_error",
                fields={"procedureTypeId": "Unbekannte Eingriffsart."},
            ) from exc
    name = _clean_text(payload.get("procedure"))
    return ProcedureType.objects.filter(name__iexact=name).first() if name else None


@transaction.atomic
def create_patient_case(payload):
    name = _clean_text(payload.get("name"))
    case_number = _clean_text(payload.get("caseNumber"))
    patient_number = _clean_text(payload.get("patientNumber")) or None

    fields = {}
    if not name:
        fields["name"] = "Name ist erforderlich."
    if not case_number:
        fields["caseNumber"] = "Fallnummer ist erforderlich."
    if fields:
        raise ApiError("Pflichtfelder fehlen.", code="validation_error", fields=fields)

    if TreatmentCase.objects.filter(case_number=case_number).exists():
        raise ApiError(
            "Diese Fallnummer existiert bereits.",
            status=409,
            code="duplicate_case_number",
            fields={"caseNumber": "Bereits vorhanden."},
        )

    patient = None
    if patient_number:
        patient = Patient.objects.filter(patient_number=patient_number).first()
        if patient and patient.name.casefold() != name.casefold():
            raise ApiError(
                "Die Patientennummer ist bereits mit einem anderen Namen verknüpft.",
                status=409,
                code="patient_number_conflict",
                fields={"patientNumber": "Bereits einem anderen Patienten zugeordnet."},
            )

    if patient is None:
        try:
            patient = Patient.objects.create(name=name, patient_number=patient_number)
        except IntegrityError as exc:
            raise ApiError(
                "Die Patientennummer existiert bereits.",
                status=409,
                code="duplicate_patient_number",
                fields={"patientNumber": "Bereits vorhanden."},
            ) from exc

    procedure_type = _procedure_type(payload)
    case = TreatmentCase.objects.create(
        patient=patient,
        case_number=case_number,
        bene_nurse=_clean_text(payload.get("beneNurse")),
        bene_deputy=_clean_text(payload.get("beneDeputy")),
        surgeon=_clean_text(payload.get("surgeon")),
        op_date=_parse_iso_date(payload.get("opDate")),
        procedure=_clean_text(payload.get("procedure")) or (procedure_type.name if procedure_type else ""),
        procedure_type=procedure_type,
    )
    create_initial_checklist_state(case)
    record_event(
        event_type="case_created",
        treatment_case=case,
        entity_type="TreatmentCase",
        entity_id=case.id,
        metadata={"caseNumber": case.case_number},
    )
    return case
