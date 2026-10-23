from django.core.management.base import BaseCommand

from apps.checklist.services import sync_checklist_texts


class Command(BaseCommand):
    help = "Gleicht die im Admin bearbeitbaren Checklisten-Texte mit definition.json ab."

    def handle(self, *args, **options):
        result = sync_checklist_texts()
        self.stdout.write(
            self.style.SUCCESS(
                f"Checklisten-Texte: {result['created']} neu, {result['updated']} aktualisiert, {result['deleted']} entfernt."
            )
        )
