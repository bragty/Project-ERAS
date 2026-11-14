from django.db import migrations, models


def strip_names_from_checklists(apps, schema_editor):
    """Stored checklist snapshots carried "<Name> · Fall <Nummer>" as label.

    Replace it with the patient ID before the name column is dropped, so no
    patient name remains anywhere in the database.
    """
    ChecklistState = apps.get_model("responses", "ChecklistState")
    for state in ChecklistState.objects.select_related("treatment_case__patient").iterator():
        data = state.state if isinstance(state.state, dict) else {}
        label = f"Patienten-ID {state.treatment_case.patient.patient_number or 'nicht erfasst'}"
        if data.get("patientName") != label:
            data["patientName"] = label
            ChecklistState.objects.filter(pk=state.pk).update(state=data)


class Migration(migrations.Migration):
    dependencies = [
        ("patients", "0003_patient_sex"),
        ("responses", "0002_alter_checkliststate_schema_version"),
    ]

    operations = [
        migrations.RunPython(strip_names_from_checklists, migrations.RunPython.noop),
        migrations.RemoveField(model_name="patient", name="name"),
        migrations.AlterModelOptions(name="patient", options={"ordering": ["patient_number"]}),
        migrations.AlterField(
            model_name="patient",
            name="patient_number",
            field=models.CharField("Patienten-ID", max_length=64, unique=True, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name="treatmentcase",
            name="case_number",
            field=models.CharField("Fallnummer (technisch)", max_length=64, unique=True),
        ),
    ]
