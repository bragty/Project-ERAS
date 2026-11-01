from apps.responses.models import ChecklistState


def case_to_dict(case, *, include_deletion=False):
    try:
        state = case.checklist_state
    except ChecklistState.DoesNotExist:
        state = None
    result = {
        "id": str(case.id),
        "patientId": str(case.patient_id),
        "name": case.patient.name,
        "patientNumber": case.patient.patient_number or "",
        "sex": case.patient.sex,
        "caseNumber": case.case_number,
        "opDate": case.op_date.isoformat() if case.op_date else "",
        "procedure": case.procedure_type.name if case.procedure_type else case.procedure,
        "procedureTypeId": case.procedure_type_id,
        "surgeon": case.surgeon,
        "beneNurse": case.bene_nurse,
        "beneDeputy": case.bene_deputy,
        "archived": case.archived,
        "progress": state.progress_total if state else 0,
        "progressPreop": state.progress_preop if state else 0,
        "progressPath": state.progress_path if state else 0,
        "complete": bool(state.complete) if state else False,
        "updatedAt": case.updated_at.isoformat(),
    }
    if include_deletion:
        from .services import patient_deletion_token
        result["deletionToken"], result["patientCaseCount"] = patient_deletion_token(case.patient)
    return result
