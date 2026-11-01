from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("patients", "0002_treatmentcase_procedure_type")]
    operations = [
        migrations.AddField(
            model_name="patient", name="sex",
            field=models.CharField("Geschlecht", max_length=6, choices=[("male", "Männlich"), ("female", "Weiblich")], blank=True, default=""),
        ),
    ]
