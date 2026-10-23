"""Clinical rules (apps/checklist/rules.py) and their use by the engine.

Ported from the former frontend tests (eras/meeting.test.cjs) when the rules
moved to the backend, plus the cases where frontend and backend used to differ.
"""

import json
from datetime import date

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.patients.models import Patient, TreatmentCase
from apps.responses.models import ChecklistState

from .definition import base_definition
from .rules import active_flags, field_required, months_before, referrals

FIELDS = base_definition()["fields"]


def required(key, answers):
    return field_required(key, FIELDS[key], answers)


class RuleTests(SimpleTestCase):
    def test_flag_thresholds_including_zero_and_empty_values(self):
        self.assertFalse(active_flags({"score_mmrc": "0", "kardio_ef": ""})["kardio"])
        self.assertTrue(active_flags({"score_mmrc": "3"})["kardio"])
        self.assertTrue(active_flags({"kardio_ef": "49"})["kardio"])
        self.assertFalse(active_flags({"score_stopbang": "2", "score_epworth": "10"})["pneumo"])
        self.assertTrue(active_flags({"score_stopbang": "3"})["pneumo"])
        self.assertTrue(active_flags({"score_epworth": "11"})["pneumo"])
        self.assertTrue(active_flags({"score_nrs": "3"})["ernaehrung"])
        self.assertFalse(active_flags({"score_nrs": "2"})["ernaehrung"])
        self.assertTrue(active_flags({"tropo_preop": "10", "tropo_tag1": "25"})["tropo"])
        self.assertFalse(active_flags({"tropo_preop": "10", "tropo_tag1": "24"})["tropo"])
        self.assertTrue(active_flags({"tropo_tag2": "71"})["tropo"])
        self.assertTrue(active_flags({"tropo_tag1": "20", "tropo_tag2": "35"})["tropo"])

    def test_conditional_required_fields(self):
        self.assertFalse(required("sucht_alkohol", {}))
        self.assertFalse(required("pbm_ansprechperson", {}))
        self.assertFalse(required("thrombo_eGFR", {}))
        self.assertFalse(required("raucher_py", {"raucher_status": "Nieraucher"}))
        self.assertTrue(required("raucher_py", {"raucher_status": "Ex-Raucher, sistiert >1 Jahr"}))
        self.assertFalse(required("raucher_menge", {"raucher_status": "Ex-Raucher, sistiert <1 Jahr"}))
        self.assertTrue(required("raucher_menge", {"raucher_status": "Aktiver Raucher"}))
        self.assertTrue(required("raucher_sistiert_seit", {"raucher_status": "Ex-Raucher, sistiert <1 Jahr"}))
        self.assertFalse(required("raucher_sistiert_seit", {"raucher_status": "Aktiver Raucher"}))
        self.assertFalse(required("pneumo_letzte_kontrolle", {"pneumo_grunderkrankung": "Keine"}))
        self.assertTrue(required("pneumo_verschlechterung", {"pneumo_grunderkrankung": "COPD"}))
        self.assertTrue(required("pneumo_niv", {}))
        self.assertTrue(required("ernaehrung_termin", {"score_nrs": "3"}))
        self.assertFalse(required("ernaehrung_termin", {"score_nrs": "2"}))
        self.assertTrue(required("operateur_termin_datum", {"operateur_termin_status": "Ja"}))
        self.assertTrue(required("vital_puls", {}))

    def test_lufu_referral_counts_exact_months(self):
        def lufu(last, disease="COPD", today=date(2026, 10, 22)):
            answers = {"pneumo_grunderkrankung": disease, "pneumo_letzte_kontrolle": last}
            entry = next(r for r in referrals(answers, [], active_flags(answers), "", today) if r["id"] == "lufu")
            return entry["required"]

        self.assertTrue(lufu("2025-10-22"))
        self.assertFalse(lufu("2025-10-23"))
        self.assertTrue(lufu("2026-04-22", "Lungenfibrose/restriktive Lungenfunktion"))
        self.assertFalse(lufu("2026-04-23", "Lungenfibrose/restriktive Lungenfunktion"))
        self.assertTrue(lufu("2026-10-01", "Neuromuskuläre Erkrankung/Tetraplegie"))
        self.assertFalse(lufu("2020-01-01", "Keine"))
        self.assertEqual(months_before(date(2026, 8, 31), 6), date(2026, 2, 28))


class EngineRuleTests(TestCase):
    def setUp(self):
        patient = Patient.objects.create(name="QA", patient_number="P-QA")
        self.case = TreatmentCase.objects.create(patient=patient, case_number="F-QA")
        self.url = reverse("responses_api:case-state", kwargs={"case_number": self.case.case_number})

    def put(self, state):
        response = self.client.put(self.url, data=json.dumps({"state": state}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_questionnaire_totals_including_zero_and_half_points(self):
        g8 = {key: max(FIELDS[key]["options"], key=lambda o: float(o["value"]))["value"] for key in
              ["g8_food", "g8_weight", "g8_mobility", "g8_neuro", "g8_bmi", "g8_medication", "g8_health", "g8_age"]}
        self.assertEqual(self.put({"answers": g8})["state"]["answers"]["score_g8"], "17")
        self.assertEqual(self.put({"answers": {**g8, "g8_health": "0.5"}})["state"]["answers"]["score_g8"], "15.5")
        self.assertEqual(self.put({"answers": {}})["state"]["answers"]["score_g8"], "")
        stopbang = {f"stopbang_{key}": "0" for key in ["snoring", "tired", "observed", "pressure", "bmi", "age", "neck", "sex"]}
        self.assertEqual(self.put({"answers": stopbang})["state"]["answers"]["score_stopbang"], "0")
        epworth = {f"epworth_{index}": "3" for index in range(8)}
        self.assertEqual(self.put({"answers": epworth})["state"]["answers"]["score_epworth"], "24")
        self.assertEqual(self.put({"answers": {**epworth, "epworth_0": "4"}})["state"]["answers"]["score_epworth"], "")

    def test_derived_results_for_the_frontend(self):
        derived = self.put({
            "opDate": "2026-10-30",
            "answers": {**{f"stopbang_{key}": "1" if key in ("snoring", "tired", "observed") else "0"
                           for key in ["snoring", "tired", "observed", "pressure", "bmi", "age", "neck", "sex"]},
                        "vital_groesse": "180", "vital_gewicht": "81",
                        "physio_neoblase": "Ja", "physio_rehakur": "Nein"},
        })["derived"]
        self.assertEqual(derived["bmi"], 25.0)
        self.assertEqual(list(derived["flagMessages"]), ["pneumo"])
        self.assertEqual(derived["flaggedFields"], ["score_epworth", "score_stopbang"])
        physio = next(r for r in derived["referrals"] if r["id"] == "physio")
        self.assertTrue(physio["required"])
        for expected in ("QA · Fall F-QA", "2026-10-30", "Beckenboden", "ViTA-Reha postoperativ"):
            self.assertIn(expected, physio["text"])
        osas = next(r for r in derived["referrals"] if r["id"] == "osas")
        self.assertTrue(osas["required"])
        self.assertEqual(next(r for r in derived["referrals"] if r["id"] == "ernaehrung")["dateField"], "ernaehrung_termin")

    def test_refused_tick_returns_the_reasons(self):
        payload = self.put({"checked": {"t1:raucher": True}, "answers": {"raucher_status": "Aktiver Raucher"}})
        self.assertNotIn("t1:raucher", payload["state"]["checked"])
        self.assertEqual(payload["validationErrors"]["t1:raucher"], {"raucher_menge": "Pflichtfeld.", "raucher_py": "Pflichtfeld."})

    def test_step_is_validated_like_the_browser_did(self):
        vitals = {"vital_rr_sys": "120", "vital_rr_dia": "80", "vital_puls": "70", "vital_spo2": "98",
                  "vital_gewicht": "70", "vital_groesse": "175"}
        payload = self.put({"checked": {"t1:vitalparameter": True}, "answers": {**vitals, "vital_temp": "37.05"}})
        self.assertIn("vital_temp", payload["validationErrors"]["t1:vitalparameter"])
        payload = self.put({"checked": {"t1:vitalparameter": True}, "answers": {**vitals, "vital_temp": "37.1"}})
        self.assertTrue(payload["state"]["checked"]["t1:vitalparameter"])

    def test_stored_states_of_old_versions_are_migrated(self):
        ChecklistState.objects.create(treatment_case=self.case, state={
            "schemaVersion": 2,
            "checked": {"t1:fb-g8": True, "t2:p-stoma:0": True},
            "answers": {"score_g8": "12", "score_ecog": "2 = gehfähig", "stoma_termin": "2026-11-01"},
        })
        state = self.client.get(self.url).json()["state"]
        self.assertEqual(state["legacyScores"], {"score_g8": "12"})
        self.assertEqual(state["answers"]["score_g8"], "")
        self.assertEqual(state["answers"]["score_ecog"], "2")
        self.assertNotIn("t1:fb-g8", state["checked"])
        # Version 2 already had the single stoma item: its tick stays.
        self.assertTrue(state["checked"]["t2:p-stoma:0"])

    def test_group_ticks_of_version_1_are_not_taken_over(self):
        ChecklistState.objects.create(treatment_case=self.case, state={
            "checked": {"t2:s-pflege:0": True, "t2:p-stoma:0": True},
            "answers": {"stoma_termin": "2026-11-01"},
        })
        self.assertEqual(self.client.get(self.url).json()["state"]["checked"], {})
