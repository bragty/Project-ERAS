# Generated for the ERAS prototype backend.
import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [("patients", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="ChecklistState",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("schema_version", models.PositiveIntegerField(default=2)),
                ("state", models.JSONField(default=dict)),
                ("progress_preop", models.PositiveSmallIntegerField(default=0)),
                ("progress_path", models.PositiveSmallIntegerField(default=0)),
                ("progress_total", models.PositiveSmallIntegerField(default=0)),
                ("complete", models.BooleanField(default=False)),
                ("validation_errors", models.JSONField(blank=True, default=dict)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "treatment_case",
                    models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="checklist_state", to="patients.treatmentcase"),
                ),
            ],
            options={"ordering": ["-updated_at"]},
        ),
    ]
