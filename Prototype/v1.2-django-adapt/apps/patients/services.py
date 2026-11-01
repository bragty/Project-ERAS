from datetime import date

from django.db import IntegrityError, transaction
from django.db.models import F
from django.core import signing
from django.utils import timezone

from apps.audit.services import record_event
from apps.checklist.models import ProcedureType
from apps.core.api import ApiError
from apps.responses.services import create_initial_checklist_state

from .models import Patient, TreatmentCase


def _clean_text(value):
    return str(value or "").strip()


def _parse_iso_date(value, field_name="opDate"):
    if value is not None and not isinstance(value, str):
        raise ApiError("Ungültiges Datum.", code="validation_error", fields={field_name: "Bitte ein gültiges Datum eingeben."})
    value = _clean_text(value)
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return parsed
    except ValueError as exc:
        raise ApiError(
            "Ungültiges Datum. Erwartet wird YYYY-MM-DD.",
            code="validation_error",
            fields={field_name: "Ungültiges Datum."},
        ) from exc


PATIENT_TEXT_FIELDS = {"name": (Patient, "name"), "patientNumber": (Patient, "patient_number"),
    "caseNumber": (TreatmentCase, "case_number"), "beneNurse": (TreatmentCase, "bene_nurse"),
    "beneDeputy": (TreatmentCase, "bene_deputy"), "surgeon": (TreatmentCase, "surgeon"),
    "procedure": (TreatmentCase, "procedure")}


def patient_form_rules():
    return {"maxLengths": {key: model._meta.get_field(attr).max_length for key, (model, attr) in PATIENT_TEXT_FIELDS.items()},
            "sexOptions": [{"value": value, "label": label} for value, label in Patient.Sex.choices]}


def _validate_patient_payload(payload, *, creating):
    errors = {}
    for key, limit in patient_form_rules()["maxLengths"].items():
        if key not in payload:
            continue
        if not isinstance(payload[key], str):
            errors[key] = "Bitte Text eingeben."
        elif len(payload[key].strip()) > limit:
            errors[key] = f"Bitte höchstens {limit} Zeichen eingeben."
    for key, label in (("name", "Name"), ("caseNumber", "Fallnummer")):
        if (creating or key in payload) and not _clean_text(payload.get(key)):
            errors[key] = f"{label} ist erforderlich."
    if (creating or "sex" in payload) and payload.get("sex") not in Patient.Sex.values:
        # Existing patients may retain an unknown value while other data is edited.
        if creating or payload.get("sex") != "":
            errors["sex"] = "Bitte Männlich oder Weiblich auswählen."
    if "opDate" in payload:
        try:
            _parse_iso_date(payload["opDate"])
        except ApiError as exc:
            errors.update(exc.fields)
    if errors:
        raise ApiError("Bitte die markierten Felder prüfen.", status=422, code="validation_error", fields=errors)


def refresh_patient_cases(patient):
    """Publish central corrections without changing stored clinical answers."""
    from apps.responses.models import ChecklistState
    from apps.responses.services import refresh_checklist_summary
    cases = TreatmentCase.objects.filter(patient=patient)
    cases.update(updated_at=timezone.now())
    for case in cases:
        if not case.archived:
            refresh_checklist_summary(case)
        ChecklistState.objects.filter(treatment_case=case).update(revision=F("revision") + 1, updated_at=timezone.now())


def patient_deletion_snapshot(patient):
    return {"patientId": str(patient.pk), "updatedAt": patient.updated_at.isoformat(),
            "cases": [{"id": str(case.pk), "updatedAt": case.updated_at.isoformat(),
                       "revision": getattr(getattr(case, "checklist_state", None), "revision", None)}
                      for case in patient.cases.select_related("checklist_state").order_by("pk")]}


def patient_deletion_token(patient):
    snapshot = patient_deletion_snapshot(patient)
    return signing.dumps(snapshot, salt="patients.delete"), len(snapshot["cases"])


@transaction.atomic
def delete_patient(treatment_case, payload):
    """Delete only the explicitly confirmed patient snapshot, keeping audit events."""
    from apps.responses.models import ChecklistState
    patient = Patient.objects.select_for_update().get(pk=treatment_case.patient_id)
    if payload.get("confirmedPatientId") != str(patient.pk):
        raise ApiError("Die Löschung muss für diesen Patienten bestätigt werden.", status=422, code="confirmation_required")
    if not isinstance(payload.get("deletionToken"), str):
        raise ApiError("Bitte die Löschbestätigung erneut öffnen.", status=422, code="confirmation_required")
    try:
        confirmed = signing.loads(payload.get("deletionToken", ""), salt="patients.delete", max_age=900)
    except (signing.BadSignature, TypeError, ValueError) as exc:
        raise ApiError("Bitte die Löschbestätigung erneut öffnen.", status=422, code="confirmation_required") from exc
    cases = list(TreatmentCase.objects.select_for_update().filter(patient=patient))
    # Lock checklist records as well: a concurrently edited case must never be
    # deleted based on the older confirmation shown in the browser.
    list(ChecklistState.objects.select_for_update().filter(treatment_case__in=cases).values_list("pk", flat=True))
    if confirmed != patient_deletion_snapshot(patient):
        raise ApiError("Patientendaten oder Checklisten wurden inzwischen geändert. Bitte erneut prüfen und die Löschung neu bestätigen.",
                       status=409, code="patient_revision_conflict")
    case_count = len(cases)
    checklist_count = ChecklistState.objects.filter(treatment_case__in=cases).count()
    record_event(event_type="patient_deleted", entity_type="Patient", entity_id=patient.pk,
                 metadata={"caseCount": case_count, "checklistCount": checklist_count})
    # These relationships deliberately use PROTECT in normal ORM operations.
    # Only this confirmed, atomic path explicitly removes the dependent records.
    ChecklistState.objects.filter(treatment_case__in=cases).delete()
    TreatmentCase.objects.filter(pk__in=[case.pk for case in cases]).delete()
    patient.delete()
    return {"deleted": True, "caseCount": case_count}


def _procedure_type(payload):
    """Eingriffsart from ``procedureTypeId`` or, for older clients, by the name
    sent as ``procedure``. No type means the full checklist."""
    type_id = payload.get("procedureTypeId")
    if type_id not in (None, ""):
        try:
            if isinstance(type_id, bool) or str(int(type_id)) != str(type_id):
                raise ValueError
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
    _validate_patient_payload(payload, creating=True)
    name = _clean_text(payload.get("name"))
    case_number = _clean_text(payload.get("caseNumber"))
    patient_number = _clean_text(payload.get("patientNumber")) or None

    if TreatmentCase.objects.filter(case_number=case_number).exists():
        raise ApiError(
            "Diese Fallnummer existiert bereits.",
            status=409,
            code="duplicate_case_number",
            fields={"caseNumber": "Bereits vorhanden."},
        )

    patient = None
    if patient_number:
        patient = Patient.objects.select_for_update().filter(patient_number=patient_number).first()
        if patient and patient.name.casefold() != name.casefold():
            raise ApiError(
                "Die Patientennummer ist bereits mit einem anderen Namen verknüpft.",
                status=409,
                code="patient_number_conflict",
                fields={"patientNumber": "Bereits einem anderen Patienten zugeordnet."},
            )
        if patient and patient.sex and patient.sex != payload["sex"]:
            raise ApiError("Das Geschlecht weicht von den gespeicherten Stammdaten ab. Bitte den bestehenden Patienten bearbeiten.",
                           status=409, code="patient_sex_conflict", fields={"sex": "Abweichung zu vorhandenen Stammdaten."})

    if patient is None:
        try:
            patient = Patient.objects.create(name=name, patient_number=patient_number, sex=payload["sex"])
        except IntegrityError as exc:
            raise ApiError(
                "Die Patientennummer existiert bereits.",
                status=409,
                code="duplicate_patient_number",
                fields={"patientNumber": "Bereits vorhanden."},
            ) from exc
    elif not patient.sex:
        patient.sex = payload["sex"]
        patient.save(update_fields=["sex", "updated_at"])
        refresh_patient_cases(patient)
        record_event(event_type="patient_updated", entity_type="Patient", entity_id=patient.pk,
                     metadata={"changedFields": ["sex"]})

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


@transaction.atomic
def update_patient_case(treatment_case, payload):
    case = TreatmentCase.objects.select_for_update().get(pk=treatment_case.pk)
    patient = Patient.objects.select_for_update().get(pk=case.patient_id)
    if payload.get("baseUpdatedAt") != case.updated_at.isoformat():
        raise ApiError("Die Stammdaten wurden inzwischen geändert. Bitte neu laden und erneut prüfen.",
                       status=409, code="patient_revision_conflict")
    _validate_patient_payload(payload, creating=False)
    if "caseNumber" in payload and payload["caseNumber"] != case.case_number:
        raise ApiError("Die Fallnummer kann hier nicht geändert werden.", status=422,
                       fields={"caseNumber": "Fallnummer bleibt unverändert."})
    patient_changed, case_changed = [], []
    for key, attr in (("name", "name"), ("patientNumber", "patient_number"), ("sex", "sex")):
        if key not in payload:
            continue
        value = _clean_text(payload[key])
        if key == "patientNumber":
            value = value or None
            if value and Patient.objects.exclude(pk=patient.pk).filter(patient_number=value).exists():
                raise ApiError("Die Patientennummer ist bereits vergeben.", status=409,
                               fields={"patientNumber": "Bereits einem anderen Patienten zugeordnet."})
        if getattr(patient, attr) != value:
            setattr(patient, attr, value)
            patient_changed.append(attr)
    # Unknown legacy sex may be filled; a known value cannot be cleared by omission/blank.
    if "sex" in patient_changed and not patient.sex:
        raise ApiError("Bitte Männlich oder Weiblich auswählen.", status=422, fields={"sex": "Geschlecht auswählen."})
    for key, attr in (("beneNurse", "bene_nurse"), ("beneDeputy", "bene_deputy"), ("surgeon", "surgeon"), ("procedure", "procedure")):
        if key in payload and getattr(case, attr) != _clean_text(payload[key]):
            setattr(case, attr, _clean_text(payload[key]))
            case_changed.append(attr)
    if "opDate" in payload:
        value = _parse_iso_date(payload["opDate"])
        if value != case.op_date:
            case.op_date = value
            case_changed.append("op_date")
    if "procedureTypeId" in payload:
        value = _procedure_type(payload)
        if value != case.procedure_type:
            case.procedure_type = value
            case_changed.append("procedure_type")
    if patient_changed:
        try:
            patient.save(update_fields=patient_changed + ["updated_at"])
        except IntegrityError as exc:
            raise ApiError("Die Patientennummer ist bereits vergeben.", status=409,
                           fields={"patientNumber": "Bereits vorhanden."}) from exc
    if case_changed:
        case.save(update_fields=case_changed + ["updated_at"])
    if "op_date" in case_changed:
        from apps.responses.models import ChecklistState
        obj = ChecklistState.objects.select_for_update().filter(treatment_case=case).first()
        if obj:
            state = dict(obj.state)
            state["opDate"] = case.op_date.isoformat() if case.op_date else ""
            obj.state = state
            obj.save(update_fields=["state"])
    if patient_changed or case_changed:
        refresh_patient_cases(patient)
        record_event(event_type="patient_updated", treatment_case=case, entity_type="Patient", entity_id=patient.pk,
                     metadata={"changedFields": sorted(patient_changed), "caseFields": sorted(case_changed)})
    return TreatmentCase.objects.select_related("patient", "procedure_type", "checklist_state").get(pk=case.pk)
