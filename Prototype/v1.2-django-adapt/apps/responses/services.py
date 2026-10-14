from copy import deepcopy
from datetime import date, datetime

from django.db import transaction

from apps.audit.services import record_event
from apps.core.api import ApiError
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


def get_revision(treatment_case):
    """Cheap lookup for clients polling for changes made on other workstations."""
    row = (
        ChecklistState.objects.filter(treatment_case=treatment_case)
        .values("revision", "updated_at")
        .first()
    )
    if row is None:
        return 0, None
    return row["revision"], row["updated_at"]


@transaction.atomic
def save_state(treatment_case, raw_state, base_revision=None):
    """Persist a full checklist state.

    When ``base_revision`` is given, the save is rejected with a conflict if
    another client saved in the meantime. The client then merges the newer
    server state into its local edits and retries, so concurrent edits on
    different fields do not overwrite each other.
    """
    from apps.checklist.lab_import.validation import validate_imported_labs
    validate_imported_labs(raw_state.get("labs") or [])
    state_obj, _ = ChecklistState.objects.select_for_update().get_or_create(
        treatment_case=treatment_case,
        defaults={"state": default_state(treatment_case)},
    )
    if base_revision is not None and base_revision != state_obj.revision:
        raise ApiError(
            "Die Checkliste wurde zwischenzeitlich an einem anderen Arbeitsplatz geändert.",
            status=409,
            code="revision_conflict",
            fields={"revision": state_obj.revision},
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

    def import_keys(state):
        keys = set()
        details = {}
        for row in state.get("labs") or []:
            meta = row.get("importMeta") if isinstance(row, dict) else None
            if not isinstance(meta, dict) or not meta.get("sourceHash") or not meta.get("labId"):
                continue
            key = (str(meta.get("sourceHash")), str(meta.get("labId")), str(meta.get("measurementAt") or ""))
            keys.add(key)
            details[key] = meta
        return keys, details

    old_imports, _old_import_details = import_keys(old_state)
    new_imports, new_import_details = import_keys(normalized)
    added_imports = new_imports - old_imports
    if added_imports:
        record_event(
            event_type="lab_import_confirmed",
            treatment_case=treatment_case,
            entity_type="ChecklistState",
            entity_id=state_obj.id,
            metadata={
                "count": len(added_imports),
                "sourceHashes": sorted({key[0][:16] for key in added_imports}),
                "labIds": sorted({key[1] for key in added_imports}),
                "measurementTimes": sorted({key[2] for key in added_imports if key[2]}),
                "revision": state_obj.revision,
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
