import uuid

from django.db import models


class AuditEvent(models.Model):
    """Technical/factual change log without user identity.

    The project deliberately has no login system. Consequently this audit trail
    records what happened and when, but not which person performed the action.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    treatment_case = models.ForeignKey(
        "patients.TreatmentCase",
        on_delete=models.SET_NULL,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    event_type = models.CharField(max_length=80)
    entity_type = models.CharField(max_length=80, blank=True)
    entity_id = models.CharField(max_length=80, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["event_type", "created_at"])]

    def __str__(self):
        return f"{self.event_type} @ {self.created_at:%Y-%m-%d %H:%M:%S}"
