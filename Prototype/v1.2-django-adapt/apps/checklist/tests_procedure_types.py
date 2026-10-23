import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.audit.models import AuditEvent
from apps.patients.models import Patient, TreatmentCase
from apps.responses.models import ChecklistState

from .definition import base_definition, filter_definition, iter_items
from .models import ProcedureType
from .schema import ALL_ITEM_IDS, PATH_ITEM_IDS, PREOP_ITEM_IDS

QUESTIONNAIRE_IDS = ["t1:fb-g8", "t1:fb-nrs", "t1:fb-ecog", "t1:fb-stopbang", "t1:fb-epworth", "t1:fb-mmrc"]


def item_ids(definition):
    return [item["id"] for _section, item in iter_items(definition)]


class FilterDefinitionTests(TestCase):
    def test_no_exclusions_keep_the_full_checklist(self):
        self.assertEqual(filter_definition(base_definition(), []), base_definition())

    def test_excluded_items_disappear_with_empty_dividers_roles_and_phases(self):
        intraop = [item_id for item_id in PATH_ITEM_IDS if item_id.startswith(("t2:i-",))]
        p_uro = [item_id for item_id in PATH_ITEM_IDS if item_id.startswith("t2:p-uro:")]
        excluded = QUESTIONNAIRE_IDS + intraop + p_uro + ["t1:pbm"]
        definition = filter_definition(base_definition(), excluded)
        self.assertEqual(item_ids(definition), [item_id for item_id in ALL_ITEM_IDS if item_id not in excluded])
        dividers = [item["divider"] for item in definition["preop"] if "divider" in item]
        self.assertNotIn("Fragebögen", dividers)
        self.assertIn("Zuweisungen & Massnahmen", dividers)
        self.assertNotIn("intraop", [phase["id"] for phase in definition["phases"]])
        praeop_roles = [role["id"] for role in definition["phases"][0]["roles"]]
        self.assertNotIn("p-uro", praeop_roles)
        self.assertIn("p-bene", praeop_roles)

    def test_divider_of_split_postop_item_goes_with_its_measures(self):
        op_tag = [item_id for item_id in PATH_ITEM_IDS if item_id.startswith("t2:s-pflege:0:sub:")]
        definition = filter_definition(base_definition(), op_tag)
        pflege = next(role for phase in definition["phases"] for role in phase["roles"] if role["id"] == "s-pflege")
        self.assertNotIn("OP-Tag", [item.get("divider") for item in pflege["items"]])
        self.assertEqual(pflege["items"][0]["divider"], "1. postoperativer Tag")


class ProcedureTypeChecklistTests(TestCase):
    def setUp(self):
        self.procedure_type = ProcedureType.objects.get(name="Funktionelle Zystektomie")
        self.procedure_type.excluded_item_ids = QUESTIONNAIRE_IDS
        self.procedure_type.save()
        patient = Patient.objects.create(name="Typ Test", patient_number="P-TYP")
        self.case = TreatmentCase.objects.create(patient=patient, case_number="F-TYP", procedure_type=self.procedure_type)

    def state_url(self):
        return reverse("responses_api:case-state", kwargs={"case_number": self.case.case_number})

    def put(self, state):
        return self.client.put(self.state_url(), data=json.dumps({"state": state}), content_type="application/json")

    def test_initial_types_are_offered_with_the_full_checklist(self):
        self.assertEqual(
            list(ProcedureType.objects.values_list("name", flat=True)),
            ["Radikale Zystektomie mit Ileum-Conduit", "Radikale Zystektomie mit Neoblase", "Funktionelle Zystektomie", "Andere Eingriffsart"],
        )
        self.assertEqual(ProcedureType.objects.exclude(name="Funktionelle Zystektomie").exclude(excluded_item_ids=[]).count(), 0)

    def test_progress_and_completion_count_only_applicable_items(self):
        applicable = [item_id for item_id in ALL_ITEM_IDS if item_id not in QUESTIONNAIRE_IDS]
        payload = self.client.get(self.state_url()).json()
        self.assertEqual(payload["summary"]["totalCount"], len(applicable))
        # A tick of an excluded item stays stored, unvalidated and uncounted.
        state = payload["state"]
        state["checked"] = {"t1:diagnosen": True, "t1:fb-g8": True}
        payload = self.put(state).json()
        self.assertTrue(payload["state"]["checked"]["t1:fb-g8"])
        self.assertNotIn("t1:fb-g8", payload["validationErrors"])
        self.assertEqual(payload["summary"]["checkedCount"], 1)
        self.assertEqual(payload["summary"]["progressPreop"], round(100 / (len(PREOP_ITEM_IDS) - len(QUESTIONNAIRE_IDS))))

    def test_checklist_page_shows_only_applicable_items(self):
        response = self.client.get(reverse("eras:checklist") + "?case=F-TYP")
        self.assertEqual(item_ids(response.context["checklist_definition"]), [i for i in ALL_ITEM_IDS if i not in QUESTIONNAIRE_IDS])
        other = TreatmentCase.objects.create(patient=self.case.patient, case_number="F-ALLE")
        response = self.client.get(reverse("eras:checklist") + f"?case={other.case_number}")
        self.assertEqual(item_ids(response.context["checklist_definition"]), ALL_ITEM_IDS)

    def test_case_creation_assigns_procedure_type(self):
        def create(case_number, **payload):
            return self.client.post(
                reverse("patients_api:patients"),
                data=json.dumps({"name": "Neu", "caseNumber": case_number, **payload}),
                content_type="application/json",
            )

        response = create("F-1", procedureTypeId=self.procedure_type.pk)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["case"]["procedure"], "Funktionelle Zystektomie")
        self.assertEqual(TreatmentCase.objects.get(case_number="F-1").procedure_type, self.procedure_type)
        # Older clients send the name only.
        create("F-2", procedure="radikale zystektomie mit neoblase")
        self.assertEqual(TreatmentCase.objects.get(case_number="F-2").procedure_type.name, "Radikale Zystektomie mit Neoblase")
        self.assertEqual(create("F-3", procedureTypeId=999999).status_code, 400)
        self.assertFalse(TreatmentCase.objects.filter(case_number="F-3").exists())

    def test_admin_configures_items_and_refreshes_running_cases(self):
        self.client.force_login(User.objects.create_superuser("arzt", "arzt@example.com", "pw"))
        url = reverse("admin:checklist_proceduretype_change", args=[self.procedure_type.pk])
        page = self.client.get(url)
        self.assertContains(page, "Prä-OP Checkliste – Fragebögen")
        self.assertContains(page, 'value="t2:s-pflege:0:sub:0"')

        self.put({"checked": {"t1:diagnosen": True}})
        included = [item_id for item_id in ALL_ITEM_IDS if item_id not in ("t1:pbm", "t1:kardio")]
        response = self.client.post(url, {"name": self.procedure_type.name, "position": 2, "active": "on", "included_items": included})
        self.assertEqual(response.status_code, 302)
        self.procedure_type.refresh_from_db()
        self.assertEqual(self.procedure_type.excluded_item_ids, ["t1:pbm", "t1:kardio"])
        state = ChecklistState.objects.get(treatment_case=self.case)
        self.assertEqual(state.progress_preop, round(100 / (len(PREOP_ITEM_IDS) - 2)))
        event = AuditEvent.objects.get(event_type="procedure_type_items_changed")
        self.assertEqual(event.metadata["excludedAdded"], ["t1:kardio", "t1:pbm"])


class EmptyProcedureTypeTests(TestCase):
    def test_admin_refuses_a_type_without_items(self):
        procedure_type = ProcedureType.objects.get(name="Andere Eingriffsart")
        self.client.force_login(User.objects.create_superuser("arzt", "arzt@example.com", "pw"))
        url = reverse("admin:checklist_proceduretype_change", args=[procedure_type.pk])
        response = self.client.post(url, {"name": procedure_type.name, "position": 3, "active": "on"})
        self.assertContains(response, "Mindestens ein Checklistenpunkt muss enthalten sein.")
        procedure_type.refresh_from_db()
        self.assertEqual(procedure_type.excluded_item_ids, [])

    def test_case_without_applicable_items_is_never_complete(self):
        procedure_type = ProcedureType.objects.create(name="Leer", excluded_item_ids=ALL_ITEM_IDS)
        patient = Patient.objects.create(name="Leer Test", patient_number="P-LEER")
        case = TreatmentCase.objects.create(patient=patient, case_number="F-LEER", procedure_type=procedure_type)
        summary = self.client.get(reverse("responses_api:case-state", kwargs={"case_number": case.case_number})).json()["summary"]
        self.assertEqual(summary["totalCount"], 0)
        self.assertFalse(summary["complete"])
        response = self.client.post(reverse("workflow_api:case-archive", kwargs={"case_number": case.case_number}), data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 409)
