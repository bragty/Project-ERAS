from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("responses", "0001_initial")]

    # Only the default for new snapshots changes. Existing JSON and versions
    # remain intact; the engine upgrades them on read/save as before.
    operations = [
        migrations.AlterField(
            model_name="checkliststate",
            name="schema_version",
            field=models.PositiveIntegerField(default=4),
        ),
    ]
