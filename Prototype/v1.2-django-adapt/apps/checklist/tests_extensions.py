"""Regression coverage for the October 2026 clinical additions."""
import json
from datetime import date
from itertools import product

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.audit.models import AuditEvent
from apps.patients.models import Patient, TreatmentCase
from apps.responses.models import ChecklistState
from .definition import base_definition
from .engine import evaluate_state, migrate_state, _validate_field
from .rules import CardiacScreeningConfig, cardiac_assessment, bowel_guidance

RISKS = base_definition()['fields']['kardio_risiken']['options']
CATEGORIES = base_definition()['fields']['kardio_kategorien']['options']


class ScreeningExtensionsTests(SimpleTestCase):
    def test_all_decision_branches_and_unknown_inputs(self):
        for acute, met, count, reviewed in product(
            ['Ja', 'Nein', 'Unbekannt', None],
            ['gt4', 'around4', 'lt4', 'unknown', None], range(6), ['Ja', 'Nein', None]
        ):
            with self.subTest(acute=acute, met=met, count=count, reviewed=reviewed):
                a = dict(kardio_akut=acute, kardio_met=met, kardio_risiken=RISKS[:count],
                         kardio_risiken_beurteilt=reviewed,
                         kardio_kategorien=CATEGORIES[:1] if acute == 'Ja' else [])
                result = cardiac_assessment(a)
                indication = acute == 'Ja' or met == 'lt4' or count > 3
                complete = acute in {'Ja', 'Nein'} and met in {'gt4', 'lt4'} and reviewed == 'Ja'
                self.assertEqual(result['status'], 'consult' if indication else 'no_recommendation' if complete else 'review')
                self.assertEqual(result['riskCount'], count)

    def test_hidden_category_is_ignored(self):
        for category in CATEGORIES:
            result = cardiac_assessment(dict(kardio_akut='Nein', kardio_met='gt4',
                kardio_kategorien=[category], kardio_risiken_beurteilt='Ja'))
            self.assertEqual(result['status'], 'no_recommendation')
            self.assertFalse(result['pending'])
        mixed = cardiac_assessment({'kardio_kategorien':[CATEGORIES[0], {'invalid':True}]})
        self.assertEqual(mixed['status'], 'review')
        self.assertTrue(mixed['pending'])

    def test_malformed_and_duplicate_risks_are_not_a_zero_risk_result(self):
        for value in ['bad', {}, [None], ['invented'], [RISKS[0], RISKS[0]]]:
            a = dict(kardio_akut='Nein', kardio_met='gt4', kardio_risiken=value, kardio_risiken_beurteilt='Ja')
            self.assertEqual(cardiac_assessment(a)['status'], 'review')
            self.assertIsNone(cardiac_assessment(a)['riskCount'])
        for value in ({}, [], True, 42):
            self.assertEqual(cardiac_assessment({'kardio_akut':value, 'kardio_met':value})['status'], 'review')

    def test_threshold_is_configurable_and_strict(self):
        a = dict(kardio_akut='Nein', kardio_met='gt4', kardio_risiken=RISKS[:3], kardio_risiken_beurteilt='Ja')
        self.assertEqual(cardiac_assessment(a)['status'], 'no_recommendation')
        self.assertEqual(cardiac_assessment(a, CardiacScreeningConfig(risk_threshold=2))['status'], 'consult')

    def test_bowel_yes_no_unknown_and_operation_dates(self):
        for status, dose in [('Ja', 2), ('Nein', 1), ('Unbekannt', None), ('', None)]:
            result = bowel_guidance({'stuhl_obstipation':status}, '2026-11-02')
            self.assertEqual(result['startDate'], '2026-10-30')
            self.assertIn('Keine Einnahme am Operationstag' if dose else 'keine Einnahme am Operationstag', result['message'])
            if dose:
                self.assertIn(f'{dose} Beutel', result['message'])
            else:
                self.assertEqual(result['status'], 'review')
                self.assertNotIn('Movicol:', result['message'])
        self.assertEqual(bowel_guidance({}, '02.11.2026')['startDate'], '2026-10-30')
        self.assertIsNone(bowel_guidance({}, 'invalid')['startDate'])


class ClinicalExtensionsPersistenceTests(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(name='Extension QA', sex='male')
        self.case = TreatmentCase.objects.create(patient=self.patient, case_number='EXT-QA', op_date=date(2026, 11, 2))
        self.url = reverse('responses_api:case-state', kwargs={'case_number': self.case.case_number})

    def put(self, state, **extra):
        response = self.client.put(self.url, data=json.dumps({'state':state, **extra}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_all_new_fields_round_trip_and_existing_answers_survive(self):
        fields = base_definition()['fields']
        answers = {'stopbang_sex':'1', 'raucher_status':'Nieraucher', 'kardio_ef':'55'}
        for key, spec in fields.items():
            if key.startswith(('anamnese_', 'untersuchung_', 'stuhl_')) or key in {
                'kardio_akut','kardio_met','kardio_risiken','kardio_kategorien','kardio_bemerkung','kardio_risiken_beurteilt'
            }:
                answers[key] = {'number':'12', 'text':'QA', 'textarea':'Mehrzeilig\nQA',
                    'physicians':[{'specialty':'Urologie', 'name':'QA'}], 'checkbox':'Ja',
                    'select':spec.get('options', [''])[0], 'multiselect':spec.get('options', [])[:1]}[spec['type']]
        answers['kardio_met'] = 'lt4'
        saved = self.put({'answers':answers, 'suchtmittel':[{'substance':'QA'}]})
        loaded = self.client.get(self.url).json()
        for key, value in answers.items():
            self.assertEqual(loaded['state']['answers'][key], value)
        self.assertEqual(saved['derived']['cardiac'], loaded['derived']['cardiac'])
        self.assertEqual(loaded['derived']['cardiac']['status'], 'consult')
        self.assertEqual(loaded['derived']['bowel']['startDate'], '2026-10-30')
        self.assertEqual(ChecklistState.objects.get(treatment_case=self.case).state['answers']['anamnese_aerzte'], answers['anamnese_aerzte'])
        event = AuditEvent.objects.filter(event_type='checklist_answers_changed').latest('created_at')
        self.assertIn('anamnese_aerzte', event.metadata['fields'])
        self.assertNotIn('Mehrzeilig', json.dumps(event.metadata))
        other = TreatmentCase.objects.create(patient=self.patient, case_number='EXT-OTHER')
        other_url = reverse('responses_api:case-state', kwargs={'case_number':other.case_number})
        self.assertNotIn('anamnese_aerzte', self.client.get(other_url).json()['state']['answers'])

    def test_male_optional_fields_preserve_values_across_context_changes(self):
        state = self.put({'answers':{'stopbang_sex':'1', 'anamnese_shim':'12', 'anamnese_sozial':'QA', 'anamnese_miktion':'QA',
                          'anamnese_stuhl':'QA', 'anamnese_gewichtsverlust':'QA', 'untersuchung_prostata':'35.5'},
                          'checked':{'t1:anamnese-alltag':True}})['state']
        self.assertTrue(state['checked']['t1:anamnese-alltag'])
        self.patient.sex='female'
        self.patient.save(update_fields=['sex'])
        state = self.put(state)['state']
        self.assertEqual(state['answers']['untersuchung_prostata'], '35.5')
        self.assertEqual(state['answers']['anamnese_shim'], '12')
        for key in ('untersuchung_prostata', 'anamnese_erektion'):
            self.assertIsNone(_validate_field(key, '', {'stopbang_sex':'1'}))

    def test_all_numeric_and_date_fields_reject_changed_invalid_input(self):
        fields=base_definition()['fields']
        for key,spec in fields.items():
            if spec['type'] not in ('number','date') or spec.get('readonly'):
                continue
            values=['abc','NaN','Infinity',True,{},[]] if spec['type']=='number' else ['2026-02-30','20261101',True,[]]
            if spec.get('min',-1)>=0:
                values.append('-1')
            if 'max' in spec:
                values.append(str(spec['max']+1))
            for value in values:
                with self.subTest(key=key,value=value):
                    response=self.client.put(self.url,data=json.dumps({'state':{'answers':{key:value}}}),content_type='application/json')
                    self.assertEqual(response.status_code,422)
                    self.assertFalse(ChecklistState.objects.filter(treatment_case=self.case).exists())

    def test_large_positive_values_do_not_gain_unapproved_medical_limits(self):
        result=self.put({'answers':{'vital_gewicht':'300.5','vital_rr_sys':'350','untersuchung_bauch':'220.0'}})
        self.assertEqual(result['state']['answers']['vital_rr_sys'],'350')

    def test_legacy_invalid_values_are_retained_and_do_not_block_other_edits(self):
        old={'answers':{'vital_spo2':'150','untersuchung_hals':'-1'},'opDate':'unbekannt'}
        ChecklistState.objects.create(treatment_case=self.case,state=old)
        loaded=self.client.get(self.url).json()
        self.assertEqual(loaded['state']['answers']['vital_spo2'],'150')
        self.assertIn('vital_spo2',loaded['validationErrors']['t1:vitalparameter'])
        state=loaded['state']
        state['answers']['anamnese_sozial']='Ergänzt'
        saved=self.put(state)
        self.assertEqual(saved['state']['answers']['vital_spo2'],'150')
        self.assertEqual(saved['state']['opDate'],'unbekannt')

    def test_manual_labs_and_worklist_dates_are_validated(self):
        for row in ({'type':'Hb','value':'-1','unit':'g/l'}, {'type':'Hb','value':'abc','unit':'g/l'},
                    {'type':'Hb','value':'Infinity','unit':'g/l'}, {'type':{},'value':'3'}, 'invalid'):
            response=self.client.put(self.url,data=json.dumps({'state':{'labs':[row]}}),content_type='application/json')
            self.assertEqual(response.status_code,422)
        self.assertEqual(self.put({'labs':[{'type':'Hb','value':'<124','unit':'g/l'}]})['state']['labs'][0]['value'],'<124')
        for state in ({'opDate':'31.02.2026'}, {'referrals':{'kardio':{'date':'2026-02-30'}}}, {'answers':[]}, {'labs':{}}):
            self.assertEqual(self.client.put(self.url,data=json.dumps({'state':state}),content_type='application/json').status_code,422)

    def test_central_sex_overrides_spoofed_questionnaire_without_losing_legacy_answer(self):
        answers={f'stopbang_{key}':'0' for key in ('snoring','tired','observed','pressure','bmi','age','neck')}
        answers['stopbang_sex']='0'
        result=self.put({'answers':answers})
        self.assertEqual(result['state']['answers']['score_stopbang'],'1')
        self.assertEqual(result['state']['answers']['stopbang_sex'],'0')
        self.patient.sex=''
        self.patient.save(update_fields=['sex'])
        result=self.client.get(self.url).json()
        self.assertEqual(result['derived']['patientSex'],'')
        self.assertEqual(result['state']['answers']['score_stopbang'],'')
        self.assertEqual(result['state']['legacyScores']['score_stopbang'],'1')

    def test_invalid_drafts_show_field_errors_and_cannot_be_completed(self):
        for key, value in [('untersuchung_hals','-1'), ('untersuchung_bauch','NaN'),
                           ('anamnese_shim','26'), ('anamnese_aerzte',[{'name':'QA'}]),
                           ('anamnese_aerzte','bad'), ('stuhl_obstipation','maybe'),
                           ('stuhl_rezept',True), ('anamnese_allergien','x'*2001)]:
            with self.subTest(key=key):
                response = self.client.put(self.url,data=json.dumps({'state':{'answers':{key:value}}}),content_type='application/json')
                self.assertEqual(response.status_code,422)
                self.assertTrue(any(key in errors for errors in response.json()['error']['fields'].values()))

    def test_legacy_state_retains_answers_notes_labs_and_item_identities(self):
        legacy = {'schemaVersion':3, 'answers':{'raucher_status':'Nieraucher', 'kardio_ef':'55', 'score_mmrc':'0'},
                  'notes':{'t1:diagnosen':'Original'}, 'labs':[{'type':'Hb','value':'124','unit':'g/l'}],
                  'checked':{'t1:diagnosen':True, 't1:kardio':True}}
        ChecklistState.objects.create(treatment_case=self.case, state=legacy, schema_version=3)
        result = self.client.get(self.url).json()
        self.assertEqual(result['state']['schemaVersion'], 4)
        self.assertEqual(result['state']['notes'], legacy['notes'])
        self.assertEqual(result['state']['labs'], legacy['labs'])
        self.assertTrue(result['state']['checked']['t1:diagnosen'])
        self.assertNotIn('t1:kardio', result['state']['checked'])
        self.assertEqual(result['derived']['cardiac']['status'], 'review')
        self.assertEqual(migrate_state(legacy)['answers'], legacy['answers'])

    def test_no_cave_interface_is_implied_and_manual_allergies_are_not_duplicated(self):
        definition = base_definition()
        item = next(i for i in definition['preop'] if i['id'] == 't1:anamnese-risiken')
        self.assertIn('Keine technische CAVE-Anbindung vorhanden', ' '.join(item['detail']))
        self.assertEqual(sum('anamnese_allergien' in i.get('fields', []) for i in definition['preop']), 1)
        saved = self.put({'answers':{'anamnese_allergien':'CAVE manuell geprüft'}})
        self.assertEqual(self.client.get(self.url).json()['state']['answers']['anamnese_allergien'],
                         saved['state']['answers']['anamnese_allergien'])

    def test_completed_screening_and_bowel_status_survive_reload(self):
        saved = self.put({'checked':{'t1:kardio':True, 't1:stuhlregulation':True}, 'answers':{
            'kardio_ef':'55', 'score_mmrc':'0', 'kardio_akut':'Nein', 'kardio_met':'gt4',
            'kardio_risiken':RISKS[:3], 'kardio_risiken_beurteilt':'Ja',
            'stuhl_obstipation':'Nein', 'stuhl_rezept':'Ja'}})
        loaded = self.client.get(self.url).json()
        self.assertTrue(loaded['state']['checked']['t1:kardio'])
        self.assertTrue(loaded['state']['checked']['t1:stuhlregulation'])
        self.assertEqual(loaded['derived']['cardiac']['status'], 'no_recommendation')
        self.assertEqual(loaded['derived']['bowel'], saved['derived']['bowel'])

    def test_old_ef_rule_remains_independent_and_new_consult_enters_worklist(self):
        for answers in ({'kardio_ef':'49'}, {'kardio_met':'lt4'}):
            result = self.put({'answers':answers})
            self.assertTrue(next(r for r in result['derived']['referrals'] if r['id']=='kardio')['required'])

    def test_hidden_categories_do_not_block_completion(self):
        result = self.put({'checked':{'t1:kardio':True}, 'answers':{
            'kardio_ef':'55', 'score_mmrc':'0', 'kardio_akut':'Nein', 'kardio_met':'gt4',
            'kardio_kategorien':CATEGORIES[:1], 'kardio_risiken_beurteilt':'Ja'}})
        self.assertIn('t1:kardio', result['state']['checked'])
        self.assertEqual(result['derived']['cardiac']['status'], 'no_recommendation')
