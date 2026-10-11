import json

from django.test import TestCase
from django.urls import reverse

from .models import Patient, TreatmentCase


class PatientApiTests(TestCase):
    def create_case(self, **overrides):
        payload = {
            "name": "Muster Anna",
            "patientNumber": "P-10021",
            "caseNumber": "F-78342",
            "opDate": "2026-08-14",
            "procedure": "Radikale Zystektomie mit Ileum-Conduit",
            "beneNurse": "Corina Frei",
            "beneDeputy": "Jessica Ambros",
            "surgeon": "Dr. Meier",
        }
        payload.update(overrides)
        return self.client.post(
            reverse("patients_api:patients"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_create_patient_and_case(self):
        response = self.create_case()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Patient.objects.count(), 1)
        self.assertEqual(TreatmentCase.objects.count(), 1)
        data = response.json()["case"]
        self.assertEqual(data["caseNumber"], "F-78342")
        self.assertEqual(data["progress"], 0)
        self.assertFalse(data["complete"])

    def test_patient_number_can_be_reused_for_second_case(self):
        self.assertEqual(self.create_case().status_code, 201)
        second = self.create_case(caseNumber="F-90000", opDate="2027-01-01")
        self.assertEqual(second.status_code, 201)
        self.assertEqual(Patient.objects.count(), 1)
        self.assertEqual(TreatmentCase.objects.count(), 2)

    def test_duplicate_case_number_is_rejected(self):
        self.assertEqual(self.create_case().status_code, 201)
        response = self.create_case()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "duplicate_case_number")

    def test_list_and_search_cases(self):
        self.create_case()
        self.create_case(name="Peter Beispiel", patientNumber="P-20000", caseNumber="F-99999")
        response = self.client.get(reverse("patients_api:patients"), {"q": "Peter", "archived": "false"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 1)
        self.assertEqual(response.json()["results"][0]["caseNumber"], "F-99999")

    def test_admin_is_not_configured(self):
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 404)
