import django.db.models.deletion
from django.db import migrations, models


def link_existing_cases(apps, schema_editor):
    """Existing cases get the Eingriffsart whose name matches their procedure text."""
    ProcedureType = apps.get_model("checklist", "ProcedureType")
    TreatmentCase = apps.get_model("patients", "TreatmentCase")
    for procedure_type in ProcedureType.objects.all():
        TreatmentCase.objects.filter(procedure__iexact=procedure_type.name).update(procedure_type=procedure_type)


class Migration(migrations.Migration):

    dependencies = [
        ("checklist", "0002_proceduretype"),
        ("patients", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="treatmentcase",
            name="procedure_type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="cases",
                to="checklist.proceduretype",
                verbose_name="Eingriffsart (Checkliste)",
            ),
        ),
        migrations.RunPython(link_existing_cases, migrations.RunPython.noop),
    ]
