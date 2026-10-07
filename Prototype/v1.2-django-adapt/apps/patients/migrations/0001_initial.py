# Generated for the ERAS prototype backend.
import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Patient",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("patient_number", models.CharField(blank=True, max_length=64, null=True, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name", "patient_number"]},
        ),
        migrations.CreateModel(
            name="TreatmentCase",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("case_number", models.CharField(max_length=64, unique=True)),
                ("bene_nurse", models.CharField(blank=True, max_length=255)),
                ("bene_deputy", models.CharField(blank=True, max_length=255)),
                ("surgeon", models.CharField(blank=True, max_length=255)),
                ("op_date", models.DateField(blank=True, null=True)),
                ("procedure", models.CharField(blank=True, max_length=255)),
                ("archived", models.BooleanField(default=False)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "patient",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cases", to="patients.patient"),
                ),
            ],
            options={"ordering": ["op_date", "case_number"]},
        ),
        migrations.AddIndex(
            model_name="treatmentcase",
            index=models.Index(fields=["archived", "op_date"], name="patients_tr_archive_3fe7c8_idx"),
        ),
        migrations.AddIndex(
            model_name="treatmentcase",
            index=models.Index(fields=["case_number"], name="patients_tr_case_nu_a6ad2c_idx"),
        ),
    ]
