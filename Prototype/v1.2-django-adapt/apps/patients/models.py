import uuid

from django.db import models


class Patient(models.Model):
    """Stable patient identity. A patient may have multiple treatment cases."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    patient_number = models.CharField(max_length=64, unique=True, null=True, blank=True)
    class Sex(models.TextChoices):
        MALE = "male", "Männlich"
        FEMALE = "female", "Weiblich"

    # Blank is reserved for legacy patients; never infer from a name/screening.
    sex = models.CharField("Geschlecht", max_length=6, choices=Sex.choices, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "patient_number"]

    def __str__(self):
        return f"{self.name} ({self.patient_number or 'ohne Patientennummer'})"


class TreatmentCase(models.Model):
    """One perioperative case for one patient."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="cases")
    case_number = models.CharField(max_length=64, unique=True)
    bene_nurse = models.CharField(max_length=255, blank=True)
    bene_deputy = models.CharField(max_length=255, blank=True)
    surgeon = models.CharField(max_length=255, blank=True)
    op_date = models.DateField(null=True, blank=True)
    procedure = models.CharField(max_length=255, blank=True)
    # Determines which checklist items apply; no type means the full checklist.
    procedure_type = models.ForeignKey(
        "checklist.ProcedureType",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cases",
        verbose_name="Eingriffsart (Checkliste)",
    )
    archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["op_date", "case_number"]
        indexes = [
            models.Index(fields=["archived", "op_date"], name="patients_tr_archive_3fe7c8_idx"),
            models.Index(fields=["case_number"], name="patients_tr_case_nu_a6ad2c_idx"),
        ]

    def __str__(self):
        return f"{self.case_number} · {self.patient.name}"
