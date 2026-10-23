from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _sync_texts(sender, **kwargs):
    from .services import sync_checklist_texts

    sync_checklist_texts()


class ChecklistConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.checklist"
    label = "checklist"

    def ready(self):
        from . import definition_checks  # noqa: F401  registers the system check
        # Every "manage.py migrate" (also on deploy) brings the editable texts
        # in line with definition.json.
        post_migrate.connect(_sync_texts, sender=self)
