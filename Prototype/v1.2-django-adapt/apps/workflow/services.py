from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_event
from apps.core.api import ApiError
from apps.responses.services import get_state

from .rules import can_archive


@transaction.atomic
def archive_case(treatment_case):
    _state_obj, _state, summary, _derived, errors = get_state(treatment_case)
    if not can_archive(summary):
        raise ApiError(
            "Der Fall kann erst archiviert werden, wenn alle Checklistenpunkte abgeschlossen sind.",
            status=409,
            code="case_not_complete",
            fields={"checklist": errors},
        )
    if not treatment_case.archived:
        treatment_case.archived = True
        treatment_case.archived_at = timezone.now()
        treatment_case.save(update_fields=["archived", "archived_at", "updated_at"])
        record_event(
            event_type="case_archived",
            treatment_case=treatment_case,
            entity_type="TreatmentCase",
            entity_id=treatment_case.id,
            metadata={"caseNumber": treatment_case.case_number},
        )
    return treatment_case


@transaction.atomic
def restore_case(treatment_case):
    if treatment_case.archived:
        treatment_case.archived = False
        treatment_case.archived_at = None
        treatment_case.save(update_fields=["archived", "archived_at", "updated_at"])
        record_event(
            event_type="case_restored",
            treatment_case=treatment_case,
            entity_type="TreatmentCase",
            entity_id=treatment_case.id,
            metadata={"caseNumber": treatment_case.case_number},
        )
    return treatment_case
