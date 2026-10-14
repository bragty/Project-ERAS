import json

from django.test import TestCase
from django.urls import reverse

from apps.patients.models import Patient, TreatmentCase
from apps.responses.models import ChecklistState


class ChecklistStateApiTests(TestCase):
    def setUp(self):
        patient = Patient.objects.create(name="Muster Anna", patient_number="P-10021")
        self.case = TreatmentCase.objects.create(patient=patient, case_number="F-78342")

    def state_url(self):
        return reverse("responses_api:case-state", kwargs={"case_number": self.case.case_number})

    def test_state_is_created_and_persisted(self):
        response = self.client.get(self.state_url())
        self.assertEqual(response.status_code, 200)
        state = response.json()["state"]
        state["answers"]["score_nrs"] = "4"
        response = self.client.put(self.state_url(), data=json.dumps({"state": state}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"]["answers"]["score_nrs"], "4")
        self.assertEqual(ChecklistState.objects.count(), 1)

    def test_questionnaire_score_is_recomputed_server_side(self):
        state = self.client.get(self.state_url()).json()["state"]
        state["answers"].update(
            {
                "g8_food": "2",
                "g8_weight": "3",
                "g8_mobility": "2",
                "g8_neuro": "2",
                "g8_bmi": "3",
                "g8_medication": "1",
                "g8_health": "2",
                "g8_age": "2",
                "g8_zuweisung": "Nein",
                "score_g8": "0",
            }
        )
        response = self.client.put(self.state_url(), data=json.dumps({"state": state}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"]["answers"]["score_g8"], "17")

    def test_invalid_checked_item_is_unchecked_by_backend(self):
        state = self.client.get(self.state_url()).json()["state"]
        state["answers"].update(
            {
                "vital_rr_sys": "120",
                "vital_rr_dia": "80",
                "vital_puls": "70",
                "vital_spo2": "150",
                "vital_temp": "37.0",
                "vital_gewicht": "70",
                "vital_groesse": "175",
            }
        )
        state["checked"]["t1:vitalparameter"] = True
        response = self.client.put(self.state_url(), data=json.dumps({"state": state}), content_type="application/json")
        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(payload["state"]["checked"].get("t1:vitalparameter", False))
        self.assertIn("t1:vitalparameter", payload["validationErrors"])

    def test_archive_is_blocked_until_checklist_complete(self):
        response = self.client.post(reverse("workflow_api:case-archive", kwargs={"case_number": self.case.case_number}), data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "case_not_complete")

    def test_schema_endpoint_reports_current_counts(self):
        response = self.client.get(reverse("checklist_api:schema"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["counts"]["preop"], 24)
        self.assertEqual(response.json()["counts"]["path"], 93)
        self.assertEqual(response.json()["counts"]["total"], 117)

    def revision_url(self):
        return reverse("responses_api:case-state-revision", kwargs={"case_number": self.case.case_number})

    def put_state(self, state, base_revision=None):
        body = {"state": state}
        if base_revision is not None:
            body["baseRevision"] = base_revision
        return self.client.put(self.state_url(), data=json.dumps(body), content_type="application/json")

    def test_revision_endpoint_reflects_saves(self):
        payload = self.client.get(self.state_url()).json()
        response = self.client.get(self.revision_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["revision"], payload["revision"])
        self.put_state(payload["state"], payload["revision"])
        self.assertEqual(self.client.get(self.revision_url()).json()["revision"], payload["revision"] + 1)

    def test_save_with_outdated_base_revision_is_rejected(self):
        payload = self.client.get(self.state_url()).json()
        first = dict(payload["state"], answers={"score_nrs": "4"})
        self.assertEqual(self.put_state(first, payload["revision"]).status_code, 200)

        # Second workstation still works on the old revision.
        second = dict(payload["state"], answers={"score_nrs": "1"})
        response = self.put_state(second, payload["revision"])
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "revision_conflict")
        self.assertEqual(self.client.get(self.state_url()).json()["state"]["answers"]["score_nrs"], "4")

    def test_save_without_base_revision_stays_compatible(self):
        state = self.client.get(self.state_url()).json()["state"]
        self.assertEqual(self.put_state(state).status_code, 200)
        self.assertEqual(self.put_state(state).status_code, 200)

    def test_invalid_base_revision_is_rejected(self):
        state = self.client.get(self.state_url()).json()["state"]
        response = self.client.put(self.state_url(), data=json.dumps({"state": state, "baseRevision": "1"}), content_type="application/json")
        self.assertEqual(response.status_code, 400)
