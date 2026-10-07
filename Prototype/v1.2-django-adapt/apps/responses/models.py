import uuid

from django.db import models

from apps.checklist.schema import CURRENT_SCHEMA_VERSION


class ChecklistState(models.Model):
    """Server-side snapshot of all answers/checkmarks for one treatment case.

    The current frontend is schema-driven JavaScript. Storing the versioned state
    as JSON keeps the prototype compatible while patient/case identity remains
    relational. Progress and completion are always recomputed on the backend.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    treatment_case = models.OneToOneField(
        "patients.TreatmentCase",
        on_delete=models.PROTECT,
        related_name="checklist_state",
    )
    schema_version = models.PositiveIntegerField(default=CURRENT_SCHEMA_VERSION)
    state = models.JSONField(default=dict)
    progress_preop = models.PositiveSmallIntegerField(default=0)
    progress_path = models.PositiveSmallIntegerField(default=0)
    progress_total = models.PositiveSmallIntegerField(default=0)
    complete = models.BooleanField(default=False)
    validation_errors = models.JSONField(default=dict, blank=True)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Checklist {self.treatment_case.case_number} (rev {self.revision})"
