import json
import csv
import io

from django.test import TestCase
from django.urls import reverse

from .models import Patient, TreatmentCase


class PatientOverviewTests(TestCase):
    def setUp(self):
        from apps.responses.models import ChecklistState
        self.url=reverse('patients_api:patients')
        self.alpha=TreatmentCase.objects.create(patient=Patient.objects.create(name='Alpha QA',sex='male'),case_number='ALPHA',op_date='2026-11-10')
        self.beta=TreatmentCase.objects.create(patient=Patient.objects.create(name='Beta QA',sex='female'),case_number='BETA',op_date='2026-11-05')
        self.missing=TreatmentCase.objects.create(patient=Patient.objects.create(name='Gamma QA'),case_number='MISSING')
        self.archived=TreatmentCase.objects.create(patient=self.alpha.patient,case_number='ARCHIVED',op_date='2026-10-03',archived=True)
        self.alpha_state=ChecklistState.objects.create(treatment_case=self.alpha,progress_total=10)
        self.beta_state=ChecklistState.objects.create(treatment_case=self.beta,progress_total=80)
        self.original={'answers':{'anamnese_aerzte':[{'specialty':'Urologie','name':'QA Name'}],
                                 'vital_gewicht':'75.0','custom/key~':[False,None,[]]},
                       'notes':{'t1:diagnosen':'Text; mit\nZeilenumbruch'},
                       'labs':[{'type':'Hb','value':'124','unit':'g/l'}],
                       'referrals':{'kardio':{'status':'Noch zu prüfen'}},'checked':{'t1:diagnosen':True}}
        self.archive_state=ChecklistState.objects.create(treatment_case=self.archived,state=self.original,complete=True,progress_total=100,schema_version=3)

    def numbers(self, **params):
        response=self.client.get(self.url,params)
        self.assertEqual(response.status_code,200)
        return [row['caseNumber'] for row in response.json()['results']]

    def export(self, **params):
        response=self.client.get(self.url,{'archived':'true','format':'csv',**params})
        self.assertEqual(response.status_code,200)
        content=b''.join(response.streaming_content).decode('utf-8-sig')
        return response,list(csv.DictReader(io.StringIO(content),delimiter=';'))

    def test_operation_and_progress_sorting_keep_missing_dates_last(self):
        self.assertEqual(self.numbers(sort='op_asc'),['BETA','ALPHA','MISSING'])
        self.assertEqual(self.numbers(sort='op_desc'),['ALPHA','BETA','MISSING'])
        self.assertEqual(self.numbers(sort='progress_asc'),['MISSING','ALPHA','BETA'])
        self.assertEqual(self.numbers(sort='progress_desc'),['BETA','ALPHA','MISSING'])
        self.assertEqual(self.numbers(sort='name_desc'),['MISSING','BETA','ALPHA'])

    def test_filters_and_search_can_be_combined_without_mixing_archive(self):
        self.assertEqual(self.numbers(opStatus='missing'),['MISSING'])
        self.assertEqual(self.numbers(opStatus='dated'),['BETA','ALPHA'])
        self.assertEqual(self.numbers(opFrom='2026-11-05',opTo='2026-11-10'),['BETA','ALPHA'])
        self.assertEqual(self.numbers(opFrom='2026-11-06',q='Alpha'),['ALPHA'])
        self.assertEqual(self.numbers(progressStatus='not_started'),['MISSING'])
        self.assertEqual(self.numbers(progressStatus='open'),['BETA','ALPHA','MISSING'])
        self.assertEqual(self.numbers(progressStatus='complete'),[])
        self.assertEqual(self.numbers(archived='true',progressStatus='complete'),['ARCHIVED'])

    def test_invalid_filter_values_and_dates_are_rejected(self):
        for params in ({'sort':'unknown'},{'progressStatus':'unknown'},{'opStatus':'unknown'},
                       {'opFrom':'2026-02-30'},{'opTo':'20261101'},
                       {'opFrom':'2026-11-10','opTo':'2026-11-05'}):
            with self.subTest(params=params):
                self.assertEqual(self.client.get(self.url,params).status_code,422)

    def test_csv_contains_all_archived_data_and_does_not_recompute_states(self):
        from apps.audit.models import AuditEvent
        AuditEvent.objects.create(treatment_case=self.archived,event_type='QA',metadata={'changed':['vital_gewicht']})
        response,rows=self.export(q='no matching name',progressStatus='not_started')
        self.assertEqual(response['Cache-Control'],'no-store')
        self.assertIn('attachment;',response['Content-Disposition'])
        self.assertEqual({row['Fallnummer'] for row in rows},{'ARCHIVED'})
        fields={(row['Datengruppe'],row['Feldpfad']):row for row in rows}
        self.assertEqual(fields[('Checkliste','/answers/anamnese_aerzte/0/name')]['Wert'],'QA Name')
        self.assertEqual(fields[('Checkliste','/answers/vital_gewicht')]['Bezeichnung'],'Gewicht (kg)')
        self.assertEqual(fields[('Checkliste','/notes/t1:diagnosen')]['Wert'],'Text; mit\nZeilenumbruch')
        self.assertEqual(fields[('Checkliste','/labs/0/value')]['Wert'],'124')
        self.assertEqual(fields[('Checkliste','/answers/custom~1key~0/0')]['Datentyp'],'boolean')
        self.assertEqual(fields[('Checkliste','/answers/custom~1key~0/1')]['Datentyp'],'null')
        self.assertEqual(fields[('Checkliste','/answers/custom~1key~0/2')]['Datentyp'],'array')
        self.assertEqual(fields[('Audit','/0/event_type')]['Wert'],'QA')
        self.archive_state.refresh_from_db()
        self.assertEqual(self.archive_state.state,self.original)
        self.assertEqual(self.archive_state.schema_version,3)
        self.assertTrue(AuditEvent.objects.filter(event_type='archived_patients_exported').exists())

    def test_export_protects_spreadsheet_formulas_and_preserves_empty_states(self):
        self.archived.patient.name='=HYPERLINK("example")'
        self.archived.patient.save(update_fields=['name'])
        empty=TreatmentCase.objects.create(patient=self.beta.patient,case_number='ARCHIVE-EMPTY',archived=True)
        _response,rows=self.export()
        self.assertTrue(all(row['Patientenname'].startswith("'=") for row in rows if row['Fallnummer']=='ARCHIVED'))
        self.assertTrue(any(row['Fallnummer']==empty.case_number and row['Datengruppe']=='Checkliste' and row['Datentyp']=='null' for row in rows))
        self.assertTrue(any(row['Feldpfad']=='/name' and row['Wert'].startswith("'=") for row in rows))
        self.assertEqual(self.client.get(self.url,{'format':'csv','archived':'false'}).status_code,422)

    def test_empty_archive_exports_headers(self):
        TreatmentCase.objects.filter(archived=True).update(archived=False)
        response=self.client.get(self.url,{'format':'csv','archived':'true'})
        content=b''.join(response.streaming_content)
        self.assertTrue(content.startswith(b'\xef\xbb\xbf'))
        self.assertEqual(len(list(csv.reader(io.StringIO(content.decode('utf-8-sig')),delimiter=';'))),1)


class PatientApiTests(TestCase):
    def create_case(self, **overrides):
        payload = {
            "name": "Muster Anna",
            "sex": "female",
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

    def test_admin_requires_login(self):
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_admin_pages_render_for_superuser(self):
        from django.contrib.auth import get_user_model

        self.create_case()
        case = TreatmentCase.objects.get(case_number="F-78342")
        admin_user = get_user_model().objects.create_superuser("admin", "admin@example.com", "pw")
        self.client.force_login(admin_user)
        for url in (
            "/admin/",
            "/admin/patients/patient/",
            f"/admin/patients/patient/{case.patient.pk}/change/",
            "/admin/patients/treatmentcase/",
            f"/admin/patients/treatmentcase/{case.pk}/change/",
            "/admin/responses/checkliststate/",
            f"/admin/responses/checkliststate/{case.checklist_state.pk}/change/",
            "/admin/audit/auditevent/",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_admin_archive_action_refuses_incomplete_case(self):
        from django.contrib.auth import get_user_model

        self.create_case()
        case = TreatmentCase.objects.get(case_number="F-78342")
        admin_user = get_user_model().objects.create_superuser("admin", "admin@example.com", "pw")
        self.client.force_login(admin_user)
        response = self.client.post(
            "/admin/patients/treatmentcase/",
            {"action": "archive_selected", "_selected_action": [case.pk]},
            follow=True,
        )
        self.assertContains(response, "Nicht archiviert")
        case.refresh_from_db()
        self.assertFalse(case.archived)

    def test_sex_is_required_and_only_supported_values_are_accepted(self):
        for value in ('', None, 'unknown', 1, [], {}):
            with self.subTest(value=value):
                response=self.create_case(sex=value)
                self.assertEqual(response.status_code,422)
                self.assertIn('sex',response.json()['error']['fields'])
        payload={'name':'QA','caseNumber':'F-NOSEX'}
        response=self.client.post(reverse('patients_api:patients'),data=json.dumps(payload),content_type='application/json')
        self.assertEqual(response.status_code,422)
        self.assertEqual(Patient.objects.count(),0)

    def test_male_and_female_are_saved_and_loaded_centrally(self):
        for sex in ('male','female'):
            response=self.create_case(sex=sex,name='QA '+sex,patientNumber='QA-'+sex,caseNumber='F-'+sex)
            self.assertEqual(response.status_code,201)
            case=TreatmentCase.objects.get(case_number='F-'+sex)
            self.assertEqual(case.patient.sex,sex)
            loaded=self.client.get(reverse('patients_api:case-detail',kwargs={'case_number':case.case_number}))
            self.assertEqual(loaded.json()['case']['sex'],sex)

    def test_conflicting_sex_on_second_case_never_overwrites_patient(self):
        self.create_case(sex='female')
        response=self.create_case(caseNumber='SECOND',sex='male')
        self.assertEqual(response.status_code,409)
        self.assertEqual(Patient.objects.get().sex,'female')
        self.assertEqual(TreatmentCase.objects.count(),1)

    def test_invalid_dates_and_text_limits_fail_without_creating_records(self):
        for changes in ({'opDate':'2026-02-30'}, {'opDate':'20261101'}, {'opDate':True},
                        {'name':' '}, {'name':'x'*256}, {'patientNumber':'x'*65},
                        {'caseNumber':'x'*65}, {'beneNurse':{}}, {'surgeon':'x'*256}):
            with self.subTest(changes=changes):
                self.assertEqual(self.create_case(**changes).status_code,422)
                self.assertEqual(Patient.objects.count(),0)

    def test_legacy_patient_can_be_corrected_without_changing_saved_answers(self):
        from apps.responses.models import ChecklistState
        patient=Patient.objects.create(name='Legacy',patient_number='LEGACY')
        cases=[TreatmentCase.objects.create(patient=patient,case_number='LEGACY-'+str(i)) for i in range(2)]
        original={'answers':{'stopbang_sex':'1','untersuchung_prostata':'35.5','anamnese_erektion':'Original'},
                  'notes':{'t1:diagnosen':'Original'}}
        for case in cases:
            ChecklistState.objects.create(treatment_case=case,state=original)
        state_url=reverse('responses_api:case-state',kwargs={'case_number':cases[0].case_number})
        self.assertEqual(self.client.get(state_url).json()['derived']['patientSex'],'')
        url=reverse('patients_api:case-detail',kwargs={'case_number':cases[0].case_number})
        for sex in ('male','female','male'):
            before=self.client.get(url).json()['case']
            response=self.client.patch(url,data=json.dumps({'sex':sex,'baseUpdatedAt':before['updatedAt']}),content_type='application/json')
            self.assertEqual(response.status_code,200)
            for case in cases:
                case.patient.refresh_from_db()
                state=ChecklistState.objects.get(treatment_case=case)
                self.assertEqual(state.state,original)
                self.assertEqual(case.patient.sex,sex)
            self.assertEqual(self.client.get(state_url).json()['derived']['patientSex'],sex)
        before=self.client.get(url).json()['case']
        self.assertEqual(self.client.patch(url,data=json.dumps({'sex':'','baseUpdatedAt':before['updatedAt']}),content_type='application/json').status_code,422)

    def test_edit_uses_revision_and_preserves_unedited_fields(self):
        self.create_case()
        case=TreatmentCase.objects.get()
        url=reverse('patients_api:case-detail',kwargs={'case_number':case.case_number})
        before=self.client.get(url).json()['case']
        response=self.client.patch(url,data=json.dumps({'sex':'male','baseUpdatedAt':before['updatedAt']}),content_type='application/json')
        self.assertEqual(response.status_code,200)
        case.refresh_from_db()
        self.assertEqual(case.surgeon,'Dr. Meier')
        self.assertEqual(case.procedure,'Radikale Zystektomie mit Ileum-Conduit')
        self.assertEqual(case.op_date.isoformat(),'2026-08-14')
        stale=self.client.patch(url,data=json.dumps({'name':'Stale','baseUpdatedAt':before['updatedAt']}),content_type='application/json')
        self.assertEqual(stale.status_code,409)
        self.assertEqual(Patient.objects.get().name,'Muster Anna')

    def test_date_correction_updates_existing_state_and_bowel_guidance(self):
        self.create_case()
        case=TreatmentCase.objects.get()
        url=reverse('patients_api:case-detail',kwargs={'case_number':case.case_number})
        before=self.client.get(url).json()['case']
        response=self.client.patch(url,data=json.dumps({'opDate':'2026-11-10','baseUpdatedAt':before['updatedAt']}),content_type='application/json')
        self.assertEqual(response.status_code,200)
        state=self.client.get(reverse('responses_api:case-state',kwargs={'case_number':case.case_number})).json()
        self.assertEqual(state['state']['opDate'],'2026-11-10')
        self.assertEqual(state['derived']['bowel']['startDate'],'2026-11-07')

    def test_legacy_unknown_sex_is_not_inferred_when_other_data_is_edited(self):
        patient=Patient.objects.create(name='Legacy')
        case=TreatmentCase.objects.create(patient=patient,case_number='LEGACY')
        url=reverse('patients_api:case-detail',kwargs={'case_number':case.case_number})
        before=self.client.get(url).json()['case']
        response=self.client.patch(url,data=json.dumps({'surgeon':'Corrected','baseUpdatedAt':before['updatedAt']}),content_type='application/json')
        self.assertEqual(response.status_code,200)
        patient.refresh_from_db()
        self.assertEqual(patient.sex,'')

    def test_delete_requires_explicit_patient_and_valid_confirmation_token(self):
        self.create_case()
        url=reverse('patients_api:case-detail',kwargs={'case_number':'F-78342'})
        case=self.client.get(url).json()['case']
        for payload in ({}, {'confirmedPatientId':case['patientId']},
                        {'confirmedPatientId':'other','deletionToken':case['deletionToken']},
                        {'confirmedPatientId':case['patientId'],'deletionToken':'invalid'},
                        {'confirmedPatientId':case['patientId'],'deletionToken':{}}):
            response=self.client.delete(url,data=json.dumps(payload),content_type='application/json')
            self.assertEqual(response.status_code,422)
            self.assertTrue(Patient.objects.filter(pk=case['patientId']).exists())

    def test_confirmed_deletion_removes_all_patient_cases_and_checklists_only(self):
        from apps.responses.models import ChecklistState
        from apps.audit.models import AuditEvent
        self.create_case()
        self.create_case(caseNumber='SECOND')
        self.create_case(caseNumber='OTHER',name='Other QA',patientNumber='P-OTHER')
        url=reverse('patients_api:case-detail',kwargs={'case_number':'F-78342'})
        case=self.client.get(url).json()['case']
        self.assertEqual(case['patientCaseCount'],2)
        audit_count=AuditEvent.objects.count()
        response=self.client.delete(url,data=json.dumps({'confirmedPatientId':case['patientId'],'deletionToken':case['deletionToken']}),content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json(),{'deleted':True,'caseCount':2})
        self.assertFalse(Patient.objects.filter(pk=case['patientId']).exists())
        self.assertEqual(list(TreatmentCase.objects.values_list('case_number',flat=True)),['OTHER'])
        self.assertEqual(ChecklistState.objects.count(),1)
        self.assertEqual(AuditEvent.objects.count(),audit_count+1)
        self.assertTrue(AuditEvent.objects.filter(event_type='patient_deleted',entity_id=case['patientId']).exists())
        self.assertEqual(self.client.delete(url,data=json.dumps({}),content_type='application/json').status_code,404)

    def test_deletion_rejects_confirmation_after_other_case_was_added(self):
        self.create_case()
        url=reverse('patients_api:case-detail',kwargs={'case_number':'F-78342'})
        case=self.client.get(url).json()['case']
        self.create_case(caseNumber='ADDED')
        response=self.client.delete(url,data=json.dumps({'confirmedPatientId':case['patientId'],'deletionToken':case['deletionToken']}),content_type='application/json')
        self.assertEqual(response.status_code,409)
        self.assertEqual(TreatmentCase.objects.count(),2)

    def test_deletion_rejects_confirmation_after_checklist_was_changed(self):
        from apps.responses.models import ChecklistState
        self.create_case()
        url=reverse('patients_api:case-detail',kwargs={'case_number':'F-78342'})
        case=self.client.get(url).json()['case']
        state=ChecklistState.objects.get()
        state.revision+=1
        state.save(update_fields=['revision'])
        response=self.client.delete(url,data=json.dumps({'confirmedPatientId':case['patientId'],'deletionToken':case['deletionToken']}),content_type='application/json')
        self.assertEqual(response.status_code,409)
        self.assertEqual(Patient.objects.count(),1)
