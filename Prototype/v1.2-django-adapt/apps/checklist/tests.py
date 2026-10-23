import json
import os
from pathlib import Path
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from apps.patients.models import Patient, TreatmentCase
from apps.responses.models import ChecklistState
from .lab_import.service import _process_pdf


class ImportApiTests(TestCase):
    def setUp(self):
        patient=Patient.objects.create(name="Import Test",patient_number="P-TEST")
        self.case=TreatmentCase.objects.create(patient=patient,case_number="F-TEST")
        self.url=reverse("responses_api:case-state",kwargs={"case_number":self.case.case_number})

    def save(self,row):
        return self.client.put(self.url,data=json.dumps({"state":{"labs":[row]}}),content_type="application/json")

    def row(self):
        return {"type":"Hb","value":"124","unit":"g/l","importMeta":{"labId":"hb","originalLabel":"Hämoglobin","sourceHash":"test","templateId":"kisim-single-result-v1"}}

    def test_valid_confirmed_import_persists(self):
        response=self.save(self.row())
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["state"]["labs"][0]["value"],"124")

    def test_invalid_import_is_not_saved(self):
        for changes in [{"type":"eGFR"},{"type":"Anderer Wert"},{"unit":"G/l"},{"value":"oops"},
                        {"importMeta":{"labId":"other"}},
                        {"importMeta":{"labId":"hb","templateId":"kisim-single-result-v1","originalLabel":"Hämatokrit"}}]:
            row=self.row();row.update(changes)
            self.assertEqual(self.save(row).status_code,422)
        self.assertFalse(ChecklistState.objects.filter(treatment_case=self.case).exists())

    def test_manual_other_unchanged(self):
        self.assertEqual(self.save({"type":"Anderer Wert","value":"positiv","unit":"qualitativ"}).status_code,200)

    def test_real_sample_ocr(self):
        # Opt-in: requires installed Tesseract and the original supplied PDF.
        fixture=os.environ.get("LAB_IMPORT_SAMPLE_PDF")
        if not fixture:
            self.skipTest("Set LAB_IMPORT_SAMPLE_PDF to run real OCR regression")
        result=_process_pdf(Path(fixture).read_bytes())
        expected={"hb":("124","g/l"),"thrombozyten":("465","G/l"),"leukozyten":("10.19","G/l"),
                  "kreatinin":("83","µmol/l"),"kalium":("5.2","mmol/l"),"natrium":("137","mmol/l"),"crp":("18","mg/l")}
        self.assertEqual({x["labId"]:(x["normalizedValue"],x["normalizedUnit"]) for x in result[0]},expected)
        self.assertEqual(result[1],["2026-08-01T11:30"])
        self.assertTrue(all(x["status"]=="review" for x in result[0]))
        # Real upload endpoint: preview only, no patient values saved.
        with patch("apps.checklist.lab_import.service._process_pdf",return_value=result):
            response=self.client.post(reverse("checklist_api:lab-import",kwargs={"case_number":self.case.case_number}),
                {"file":SimpleUploadedFile("Labor.pdf",Path(fixture).read_bytes(),content_type="application/pdf")})
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.json()["suggestions"]),7)
        self.assertEqual(response.json()["patientMatch"]["status"],"unverified")
        self.assertEqual(ChecklistState.objects.get(treatment_case=self.case).state["labs"],[])


class NoteTests(TestCase):
    def test_notes_are_cut_to_max_length_and_unknown_items_dropped(self):
        from .engine import NOTE_MAX_LENGTH
        patient = Patient.objects.create(name="Notiz Test", patient_number="P-NOTE")
        case = TreatmentCase.objects.create(patient=patient, case_number="F-NOTE")
        url = reverse("responses_api:case-state", kwargs={"case_number": case.case_number})
        notes = {"t1:diagnosen": "x" * (NOTE_MAX_LENGTH + 50), "t1:pbm": "kurz", "unbekannt": "weg", "t1:medikamente": 42}
        response = self.client.put(url, data=json.dumps({"state": {"notes": notes}}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"]["notes"], {"t1:diagnosen": "x" * NOTE_MAX_LENGTH, "t1:pbm": "kurz"})
        self.assertEqual(ChecklistState.objects.get(treatment_case=case).state["notes"]["t1:diagnosen"], "x" * NOTE_MAX_LENGTH)


class ChecklistTextTests(TestCase):
    """Texts are editable in the admin; structure and IDs stay in definition.json."""

    def setUp(self):
        from .services import sync_checklist_texts
        sync_checklist_texts()

    def text(self, key):
        from .models import ChecklistText
        return ChecklistText.objects.get(key=key)

    def edit(self, key, value):
        row = self.text(key)
        row.text = value
        row.save()

    def find_item(self, definition, item_id):
        from .definition import iter_items
        return next(item for _section, item in iter_items(definition) if item["id"] == item_id)

    def test_sync_mirrors_all_texts_and_is_idempotent(self):
        from .definition import text_entries
        from .models import ChecklistText
        from .services import sync_checklist_texts
        entries = text_entries()
        self.assertEqual(ChecklistText.objects.count(), len(entries))
        self.assertEqual(len({entry["key"] for entry in entries}), len(entries))
        self.assertTrue(all(len(entry["location"]) <= 500 for entry in entries))
        self.assertEqual(sync_checklist_texts(), {"created": 0, "updated": 0, "deleted": 0})

    def test_without_overrides_the_code_definition_is_used(self):
        from .definition import base_definition
        from .services import effective_definition
        self.assertEqual(effective_definition(), base_definition())

    def test_edited_texts_are_applied_without_changing_ids(self):
        from .definition import base_definition
        from .schema import ALL_ITEM_IDS
        from .services import effective_definition
        self.edit("t1:pbm|title", "PBM einleiten")
        self.edit("t2:p-uro:0|detail", "Erste Zeile\n\n  Zweite Zeile  ")
        self.edit("t1:fb-ecog|detail", "")
        self.edit("field:raucher_status|option:Aktiver Raucher", "Raucht aktuell")
        self.edit("phase:praeop|title", "Vor der Operation")
        definition = effective_definition()
        self.assertEqual(self.find_item(definition, "t1:pbm")["title"], "PBM einleiten")
        self.assertEqual(self.find_item(definition, "t2:p-uro:0")["detail"], ["Erste Zeile", "Zweite Zeile"])
        self.assertNotIn("detail", self.find_item(definition, "t1:fb-ecog"))
        self.assertIn({"value": "Aktiver Raucher", "label": "Raucht aktuell"}, definition["fields"]["raucher_status"]["options"])
        self.assertEqual(definition["phases"][0]["title"], "Vor der Operation")
        # The code definition itself stays untouched.
        self.assertNotEqual(self.find_item(base_definition(), "t1:pbm")["title"], "PBM einleiten")
        from .definition import iter_items
        self.assertEqual([item["id"] for _section, item in iter_items(definition)], ALL_ITEM_IDS)

    def test_checklist_page_embeds_the_edited_definition(self):
        patient = Patient.objects.create(name="Text Test", patient_number="P-TEXT")
        TreatmentCase.objects.create(patient=patient, case_number="F-TEXT")
        self.edit("t1:drink|title", "Information <Drink> & Co")
        response = self.client.get(reverse("eras:checklist") + "?case=F-TEXT")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="checklist-definition"')
        # json_script escapes HTML characters, so edited texts cannot break out of the script tag.
        self.assertNotContains(response, "<Drink>")
        html = response.content.decode()
        start = html.index('<script id="checklist-definition" type="application/json">')
        payload = html[html.index(">", start) + 1:html.index("</script>", start)]
        self.assertEqual(self.find_item(json.loads(payload), "t1:drink")["title"], "Information <Drink> & Co")

    def test_sync_follows_code_defaults_unless_text_was_edited(self):
        from .models import ChecklistText
        from .services import sync_checklist_texts
        untouched = self.text("t1:diagnosen|title")
        ChecklistText.objects.filter(pk=untouched.pk).update(default_text="Alt", text="Alt")
        self.edit("t1:medikamente|title", "Eigener Titel")
        ChecklistText.objects.filter(key="t1:medikamente|title").update(default_text="Alt")
        ChecklistText.objects.create(key="t1:entfernt|title", kind="title", section="x", location="x", default_text="x", text="x")
        self.assertEqual(sync_checklist_texts()["deleted"], 1)
        self.assertEqual(self.text("t1:diagnosen|title").text, "Vervollständigung Diagnosenliste")
        edited = self.text("t1:medikamente|title")
        self.assertEqual((edited.text, edited.default_text), ("Eigener Titel", "Vervollständigung Medikamentenliste"))

    def test_admin_edits_texts_and_rejects_empty_titles(self):
        from django.contrib.auth.models import User
        self.client.force_login(User.objects.create_superuser("admin", "admin@example.com", "pw"))
        self.assertEqual(self.client.get(reverse("admin:checklist_checklisttext_changelist")).status_code, 200)
        row = self.text("t1:pbm|title")
        url = reverse("admin:checklist_checklisttext_change", args=[row.pk])
        self.assertEqual(self.client.post(url, {"text": "  "}).status_code, 200)
        self.assertEqual(self.text("t1:pbm|title").text, row.default_text)
        self.assertEqual(self.client.post(url, {"text": "PBM einleiten"}).status_code, 302)
        self.assertEqual(self.text("t1:pbm|title").text, "PBM einleiten")
        detail = self.text("t1:pbm|detail")
        url = reverse("admin:checklist_checklisttext_change", args=[detail.pk])
        self.assertEqual(self.client.post(url, {"text": ""}).status_code, 302)
