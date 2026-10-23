from django.db import models


class ChecklistText(models.Model):
    """One editable checklist text (title, hint, label, option …).

    Rows are created and kept in sync from ``definition.json`` by
    ``services.sync_checklist_texts()``; only ``text`` is edited in the admin.
    A row whose ``text`` differs from ``default_text`` overrides the code default.
    """

    class Kind(models.TextChoices):
        TITLE = "title", "Titel"
        DETAIL = "detail", "Hinweise"
        LABEL = "label", "Feldbeschriftung"
        PLACEHOLDER = "placeholder", "Platzhalter"
        OPTION = "option", "Auswahloption"
        DIVIDER = "divider", "Zwischentitel"
        PHASE_TAG = "phase_tag", "Phasen-Kennzeichnung"
        PHASE_TITLE = "phase_title", "Phasentitel"
        ROLE_TITLE = "role_title", "Berufsgruppe"
        ROLE_NOTE = "role_note", "Zusatz Berufsgruppe"

    key = models.CharField(max_length=200, unique=True, editable=False)
    position = models.PositiveIntegerField(default=0, editable=False)
    kind = models.CharField("Art", max_length=20, choices=Kind.choices, editable=False)
    section = models.CharField("Bereich", max_length=100, editable=False)
    location = models.CharField("Ort", max_length=500, editable=False)
    default_text = models.TextField("Standardtext", editable=False)
    text = models.TextField("Text", blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position"]
        verbose_name = "Checklisten-Text"
        verbose_name_plural = "Checklisten-Texte"

    def __str__(self):
        return self.location

    @property
    def is_customized(self):
        return self.text != self.default_text


class ProcedureType(models.Model):
    """Eingriffsart with the checklist items that do not apply to it.

    Exclusions (not inclusions) are stored, so a type that was never configured
    and every item added to definition.json later are part of the checklist.
    """

    name = models.CharField("Bezeichnung", max_length=255, unique=True)
    active = models.BooleanField("Bei neuen Fällen wählbar", default=True)
    position = models.PositiveIntegerField("Reihenfolge", default=0)
    excluded_item_ids = models.JSONField("Ausgeschlossene Checklistenpunkte", default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "name"]
        verbose_name = "Eingriffsart"
        verbose_name_plural = "Eingriffsarten"

    def __str__(self):
        return self.name
