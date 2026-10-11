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
