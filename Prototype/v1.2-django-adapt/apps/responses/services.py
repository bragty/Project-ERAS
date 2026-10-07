from copy import deepcopy
from datetime import date, datetime

from django.db import transaction

from apps.audit.services import record_event
from apps.checklist.engine import default_state, evaluate_state

from .models import ChecklistState


def _parse_state_op_date(raw):
    if not raw:
        return None
    raw = str(raw).strip()
    for parser in (
        lambda value: date.fromisoformat(value),
        lambda value: datetime.strptime(value, "%d.%m.%Y").date(),
    ):
        try:
            return parser(raw)
        except ValueError:
            pass
    return None


def create_initial_checklist_state(treatment_case):
    state, summary, _derived, errors = evaluate_state(default_state(treatment_case), treatment_case)
    return ChecklistState.objects.create(
        treatment_case=treatment_case,
        state=state,
        schema_version=state["schemaVersion"],
        progress_preop=summary["progressPreop"],
        progress_path=summary["progressPath"],
        progress_total=summary["progress"],
        complete=summary["complete"],
        validation_errors=errors,
    )


def get_state(treatment_case):
    state_obj, _ = ChecklistState.objects.get_or_create(
        treatment_case=treatment_case,
        defaults={"state": default_state(treatment_case)},
    )
    normalized, summary, derived, errors = evaluate_state(state_obj.state, treatment_case)
    return state_obj, normalized, summary, derived, errors


@transaction.atomic
def save_state(treatment_case, raw_state):
    state_obj, _ = ChecklistState.objects.select_for_update().get_or_create(
        treatment_case=treatment_case,
        defaults={"state": default_state(treatment_case)},
    )
    old_state = deepcopy(state_obj.state or {})
    normalized, summary, derived, errors = evaluate_state(raw_state, treatment_case)

    state_obj.state = normalized
    state_obj.schema_version = normalized["schemaVersion"]
    state_obj.progress_preop = summary["progressPreop"]
    state_obj.progress_path = summary["progressPath"]
    state_obj.progress_total = summary["progress"]
    state_obj.complete = summary["complete"]
    state_obj.validation_errors = errors
    state_obj.revision += 1
    state_obj.save()

    raw_op_date = str(normalized.get("opDate") or "").strip()
    parsed_date = _parse_state_op_date(raw_op_date)
    if not raw_op_date and treatment_case.op_date is not None:
        treatment_case.op_date = None
        treatment_case.save(update_fields=["op_date", "updated_at"])
    elif parsed_date and parsed_date != treatment_case.op_date:
        treatment_case.op_date = parsed_date
        treatment_case.save(update_fields=["op_date", "updated_at"])

    old_checked = {key for key, value in (old_state.get("checked") or {}).items() if value}
    new_checked = {key for key, value in (normalized.get("checked") or {}).items() if value}
    if old_checked != new_checked:
        record_event(
            event_type="checklist_completion_changed",
            treatment_case=treatment_case,
            entity_type="ChecklistState",
            entity_id=state_obj.id,
            metadata={
                "checkedAdded": sorted(new_checked - old_checked),
                "checkedRemoved": sorted(old_checked - new_checked),
                "revision": state_obj.revision,
                "progress": summary["progress"],
                "complete": summary["complete"],
            },
        )
    return state_obj, normalized, summary, derived, errors


@transaction.atomic
def reset_state(treatment_case):
    state_obj, normalized, summary, derived, errors = save_state(treatment_case, default_state(treatment_case))
    record_event(
        event_type="checklist_reset",
        treatment_case=treatment_case,
        entity_type="ChecklistState",
        entity_id=state_obj.id,
        metadata={"revision": state_obj.revision},
    )
    return state_obj, normalized, summary, derived, errors
