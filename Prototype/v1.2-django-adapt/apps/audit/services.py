from .models import AuditEvent


def record_event(*, event_type, treatment_case=None, entity_type="", entity_id="", metadata=None):
    """Persist a minimal audit event without storing a user identity.

    Avoid writing the full medical state into the audit log. Metadata should
    contain only structural information such as changed keys/counts.
    """
    return AuditEvent.objects.create(
        treatment_case=treatment_case,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id or ""),
        metadata=metadata or {},
    )
