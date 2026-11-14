"""Optional browser regression: playwright + chromium; isolated temporary DB only.

Run from the project directory: python eras/clinical-smoke.py
"""
import os
import csv
import io
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from playwright.sync_api import sync_playwright, expect

    with tempfile.TemporaryDirectory(prefix='bene-clinical-qa-') as folder:
        # Explicitly replace all DB configuration; never use the user's database.
        os.environ.pop('POSTGRES_DB', None)
        os.environ.update(SQLITE_PATH=str(Path(folder) / 'qa.sqlite3'),
                          DJANGO_SETTINGS_MODULE='eras_project.settings', DJANGO_ENV='development',
                          DJANGO_DEBUG='true', DJANGO_ALLOWED_HOSTS='127.0.0.1,localhost')
        import django
        django.setup()
        from django.core.management import call_command
        from django.db import connections
        from apps.patients.models import Patient, TreatmentCase
        from apps.responses.models import ChecklistState
        call_command('migrate', verbosity=0, interactive=False)
        TreatmentCase.objects.create(patient=Patient.objects.create(patient_number='P-BROWSER-QA'),
                                     case_number='BROWSER-QA', op_date='2026-11-10')
        sort_case=TreatmentCase.objects.create(patient=Patient.objects.create(patient_number='P-SORT',sex='female'),case_number='BROWSER-SORT',op_date='2026-11-05',surgeon='Dr. Sort')
        ChecklistState.objects.create(treatment_case=sort_case,progress_total=80)
        for suffix in ('A','B'):
            archived=TreatmentCase.objects.create(patient=Patient.objects.create(patient_number='P-ARCHIVED-'+suffix,sex='female'),case_number='ARCHIVE-QA-'+suffix,archived=True,op_date='2026-10-03')
            ChecklistState.objects.create(treatment_case=archived,complete=True,progress_total=100,
                                          state={'notes':{'t1:diagnosen':'CSV QA;\nNotiz'},'labs':[{'type':'Hb','value':'124','unit':'g/l'}]})
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        origin = f'http://127.0.0.1:{port}'
        with open(Path(folder) / 'server.log', 'w') as log:
            server = subprocess.Popen([sys.executable, 'manage.py', 'runserver', f'127.0.0.1:{port}', '--noreload'],
                                      cwd=ROOT, env=os.environ.copy(), stdout=log, stderr=log)
            try:
                for _ in range(100):
                    try:
                        urlopen(origin+'/api/health/', timeout=1).close()
                        break
                    except OSError:
                        time.sleep(.1)
                with sync_playwright() as pw:
                    browser = pw.chromium.launch()
                    page = browser.new_page(viewport={'width':1280, 'height':900})
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(origin+'/')
                    modal=page.locator('#patientModal')
                    page.locator('#newPatientBtn').click()
                    page.locator('#closePatientModal').click()
                    expect(modal).not_to_have_class('modal-backdrop open')
                    page.locator('#newPatientBtn').click()
                    page.locator('#newPatientNumber').fill('Ungespeicherte QA Eingabe')
                    page.mouse.click(3,3)
                    expect(modal).to_have_class('modal-backdrop open')
                    page.keyboard.press('Escape')
                    expect(modal).to_have_class('modal-backdrop open')
                    page.locator('#closePatientModal').click()
                    expect(page.locator('#patientDiscardConfirmation')).to_be_visible()
                    page.locator('#continuePatientEditing').click()
                    expect(page.locator('#newPatientNumber')).to_have_value('Ungespeicherte QA Eingabe')
                    page.locator('#cancelPatientModal').click()
                    page.locator('#discardPatientChanges').click()
                    expect(modal).not_to_have_class('modal-backdrop open')
                    # Shared modal layout, long labels, reserved error rows and Tab loop.
                    page.locator('#newPatientBtn').click()
                    page.locator('#savePatient').click()
                    for width in (1280,768,390,320):
                        page.set_viewport_size({'width':width,'height':900})
                        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), f'Modal overflow at {width}px'
                        if os.getenv('BENE_QA_SCREENSHOTS'):
                            target=Path(os.environ['BENE_QA_SCREENSHOTS'])
                            target.mkdir(parents=True,exist_ok=True)
                            page.locator('.modal').screenshot(path=str(target/f'patient-modal-{width}.png'))
                    page.set_viewport_size({'width':1280,'height':900})
                    page.locator('#savePatient').focus()
                    page.keyboard.press('Tab')
                    expect(page.locator('#closePatientModal')).to_be_focused()
                    page.locator('#closePatientModal').click()
                    for sex in ('male','female'):
                        page.locator('#newPatientBtn').click()
                        expect(page.locator('#deletePatient')).to_be_hidden()
                        page.locator('#savePatient').click()
                        expect(page.locator('#newPatientSexError')).to_contain_text('auswählen')
                        expect(page.locator('#newPatientNumberError')).to_contain_text('Patienten-ID ist erforderlich')
                        # Neither a name nor a case number can be entered any more.
                        expect(page.locator('#newPatientName')).to_have_count(0)
                        expect(page.locator('#newCaseNumber')).to_have_count(0)
                        page.locator('#newPatientNumber').fill('P-'+sex.upper())
                        page.locator('#newPatientSex').select_option(sex)
                        page.locator('#savePatient').click()
                        expect(modal).not_to_have_class('modal-backdrop open')
                        expect(page.locator('#patientSearchResults')).to_contain_text('P-'+sex.upper())
                        expect(page.locator('#patientSearchResults')).not_to_contain_text('P-'+sex.upper()+'-1')
                    page.locator('#newPatientBtn').click()
                    page.locator('#newPatientNumber').fill('P-MALE')
                    page.locator('#newPatientSex').select_option('female')
                    page.locator('#savePatient').click()
                    expect(page.locator('#newPatientSexError')).to_contain_text('Abweichung')
                    expect(page.locator('#newPatientNumber')).to_have_value('P-MALE')
                    page.locator('#newPatientNumber').fill('P-EXTRA')
                    page.locator('#savePatient').click()
                    expect(modal).not_to_have_class('modal-backdrop open')
                    # Deletion always requires its own explicit confirmation.
                    page.locator('[data-edit-case="P-EXTRA-1"]').click()
                    expect(page.locator('#deletePatient')).to_be_visible()
                    page.locator('#newPatientNumber').fill('Unsaved local id')
                    page.locator('#deletePatient').click()
                    expect(page.locator('#patientDeleteDescription')).to_contain_text('P-EXTRA')
                    page.keyboard.press('Escape')
                    expect(page.locator('#patientDeleteConfirmation')).to_be_visible()
                    page.locator('#cancelPatientDelete').click()
                    expect(page.locator('#newPatientNumber')).to_have_value('Unsaved local id')
                    page.locator('#deletePatient').click()
                    page.locator('#confirmPatientDelete').click()
                    expect(modal).not_to_have_class('modal-backdrop open')
                    expect(page.locator('[data-case-number="P-EXTRA-1"]')).to_have_count(0)
                    expect(page.locator('[data-case-number="P-MALE-1"]')).to_have_count(1)
                    # The original overview and row actions coexist with the sidebar.
                    expect(page.locator('.sidebar nav').locator('button,a')).to_have_count(2)
                    expect(page.locator('.sidebar a[href="/admin/"]')).to_have_count(0)
                    page.locator('#patientSort').select_option('progress_desc')
                    expect(page.locator('[data-case-number]').first).to_have_attribute('data-case-number','BROWSER-SORT')
                    page.locator('#opDateStatus').select_option('missing')
                    expect(page.locator('[data-case-number]')).to_have_count(2)
                    page.locator('#patientSearch').fill('female')
                    expect(page.locator('[data-case-number]')).to_have_count(1)
                    expect(page.locator('[data-case-number]')).to_have_attribute('data-case-number','P-FEMALE-1')
                    page.locator('#resetPatientFilters').click()
                    # Filter and sort by surgeon.
                    page.locator('#surgeonFilter').select_option('Dr. Sort')
                    expect(page.locator('[data-case-number]')).to_have_count(1)
                    expect(page.locator('[data-case-number]')).to_have_attribute('data-case-number','BROWSER-SORT')
                    page.locator('#resetPatientFilters').click()
                    page.locator('#patientSort').select_option('surgeon_asc')
                    expect(page.locator('[data-case-number]').first).to_have_attribute('data-case-number','BROWSER-SORT')
                    page.locator('#resetPatientFilters').click()
                    page.locator('#opDateFrom').fill('2026-11-06')
                    page.locator('#opDateTo').fill('2026-11-10')
                    page.locator('#opDateTo').press('Tab')
                    expect(page.locator('[data-case-number]')).to_have_count(1)
                    expect(page.locator('[data-case-number]')).to_have_attribute('data-case-number','BROWSER-QA')
                    page.locator('#opDateFrom').fill('2026-11-11')
                    page.locator('#opDateFrom').press('Tab')
                    expect(page.locator('#patientFilterError')).to_contain_text('Enddatum')
                    page.locator('#resetPatientFilters').click()
                    for width in (1280,1024,768,390,320):
                        page.set_viewport_size({'width':width,'height':1000})
                        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), f'Overview overflow at {width}px'
                        if os.getenv('BENE_QA_SCREENSHOTS'):
                            page.screenshot(path=str(Path(os.environ['BENE_QA_SCREENSHOTS'])/f'overview-{width}.png'),full_page=True)
                    page.set_viewport_size({'width':1280,'height':900})
                    page.locator('#archiveFilter').click()
                    expect(page.locator('#patientListTitle')).to_have_text('Archivierte Patienten')
                    expect(page.locator('[data-case-number]')).to_have_count(2)
                    expect(page.locator('#archiveFilter')).to_have_attribute('aria-current','page')
                    # Export is explicitly all archived cases, even with a search yielding none.
                    page.locator('#patientSearch').fill('no matching case')
                    expect(page.locator('[data-case-number]')).to_have_count(0)
                    with page.expect_download() as download_info:
                        page.locator('#exportArchiveCsv').click()
                    download=download_info.value
                    data=Path(download.path()).read_text(encoding='utf-8-sig')
                    exported=list(csv.DictReader(io.StringIO(data),delimiter=';'))
                    assert {row['Fallnummer (technisch)'] for row in exported}=={'ARCHIVE-QA-A','ARCHIVE-QA-B'}
                    assert 'Patientenname' not in exported[0]
                    assert any(row['Wert']=='CSV QA;\nNotiz' for row in exported)
                    page.locator('#resetPatientFilters').click()
                    page.reload()
                    expect(page.locator('#patientListTitle')).to_have_text('Archivierte Patienten')
                    expect(page.locator('[data-case-number]')).to_have_count(2)
                    if os.getenv('BENE_QA_SCREENSHOTS'):
                        page.screenshot(path=str(Path(os.environ['BENE_QA_SCREENSHOTS'])/'archive-1280.png'),full_page=True)
                    page.locator('[data-archive-case="ARCHIVE-QA-A"]').click()
                    expect(page.locator('[data-case-number]')).to_have_count(1)
                    page.locator('#overviewNav').click()
                    expect(page.locator('[data-case-number="ARCHIVE-QA-A"]')).to_have_count(1)
                    expect(page.locator('#archiveExport')).to_be_hidden()
                    # Unknown legacy patient: no inference from any old questionnaire.
                    page.goto(origin+'/checklist/?case=BROWSER-QA')
                    expect(page.locator('#pname')).to_have_value('Patienten-ID P-BROWSER-QA')
                    for removed in ('untersuchung_prostata', 'untersuchung_sturz'):
                        expect(page.locator(f'[data-fkey="{removed}"]')).to_have_count(0)
                    prostate = page.locator('[data-fkey="anamnese_erektion"]')  # male-only field
                    expect(prostate).to_be_hidden()
                    expect(page.locator('#patientContext')).to_contain_text('nicht erfasst')
                    page.locator('#patientContext a').click()
                    page.locator('#newPatientSex').select_option('male')
                    page.locator('#savePatient').click()
                    expect(modal).not_to_have_class('modal-backdrop open')
                    page.goto(origin+'/checklist/?case=BROWSER-QA')
                    expect(prostate).to_be_visible()
                    expect(page.locator('[data-fkey="stopbang_sex"]')).to_have_count(0)
                    number=page.locator('[data-fkey="vital_gewicht"]')
                    for invalid in ('-1','abc','NaN','3000'):
                        number.fill(invalid)
                        number.blur()
                        expect(number).to_have_value(invalid)
                        expect(number).to_have_attribute('aria-invalid','true')
                        expect(page.locator('#saveState')).to_contain_text('Nicht gespeichert')
                    number.fill('250.5')
                    expect(number).to_have_attribute('aria-invalid','false')
                    page.locator('#opdate').fill('31.02.2026')
                    expect(page.locator('#opdateError')).to_contain_text('gültiges OP-Datum')
                    expect(page.locator('#opdate')).to_have_value('31.02.2026')
                    page.locator('#opdate').fill('2026-11-10')
                    expect(page.locator('#opdateError')).to_be_empty()
                    page.locator('[data-lab-key="type"]').first.select_option('Hb')
                    lab=page.locator('[data-lab-key="value"]').first
                    lab.fill('-1')
                    page.locator('[data-lab-key="unit"]').first.fill('g/l')
                    expect(page.locator('#saveState')).to_contain_text('Nicht gespeichert')
                    expect(lab).to_have_value('-1')
                    expect(lab.locator('..').locator('.field-error')).to_contain_text('Nichtnegativen')
                    lab.fill('<124')
                    expect(page.locator('#saveState')).to_contain_text('Automatisch gespeichert')
                    expect(lab.locator('..').locator('.field-error')).to_be_empty()
                    prostate.fill('QA Erektion')
                    page.locator('[data-fkey="anamnese_allergien"]').fill('QA Allergie')
                    page.locator('[data-add-doctor]').click()
                    page.locator('[data-doctor-field="specialty"]').fill('Urologie')
                    page.locator('[data-doctor-field="name"]').fill('QA Arzt')
                    page.locator('[data-fkey="stuhl_obstipation"]').select_option('Ja')
                    page.locator('[data-checkbox-key="stuhl_rezept"]').check()
                    expect(page.locator('[data-bowel-result]')).to_contain_text('2 Beutel')
                    expect(page.locator('[data-bowel-result]')).to_contain_text('2026-11-07')
                    def field(key):
                        return page.locator(f'[data-fkey="{key}"]')

                    field('vital_groesse').fill('180')
                    field('vital_gewicht').fill('81')
                    expect(field('g8_bmi')).to_have_value('3')
                    expect(field('stopbang_bmi')).to_have_value('0')
                    field('vital_gewicht').fill('120')
                    expect(field('stopbang_bmi')).to_have_value('1')
                    field('raucher_status').select_option('Ex-Raucher, sistiert <1 Jahr')
                    expect(field('raucher_sistiert_seit')).to_be_visible()
                    field('raucher_menge').fill('10')
                    field('raucher_jahre').fill('15')
                    expect(field('raucher_py')).to_have_value('7.5')
                    field('raucher_status').select_option('Nieraucher')
                    for key in ('raucher_menge', 'raucher_jahre', 'raucher_py', 'raucher_sistiert_seit'):
                        expect(field(key)).to_be_hidden()
                    field('kardio_akut').select_option('Ja')
                    categories = page.locator('[data-multi-key="kardio_kategorien"]').first
                    expect(categories).to_be_visible()
                    page.locator('[data-fkey="kardio_akut"]').select_option('Nein')
                    expect(categories).to_be_hidden()
                    page.locator('[data-fkey="kardio_met"]').select_option('gt4')
                    page.locator('[data-fkey="kardio_risiken_beurteilt"]').select_option('Ja')
                    risks = page.locator('[data-multi-key="kardio_risiken"]')
                    for index in range(4):
                        risks.nth(index).check()
                    expect(page.locator('[data-cardiac-result]')).to_contain_text('Kardiologische Zuweisung erforderlich')
                    expect(page.locator('[data-cardiac-result]')).to_contain_text('4 (vollständig überprüft)')
                    referral = page.locator('[data-referral-id="kardio"] textarea').input_value()
                    for index in range(4):
                        assert risks.nth(index).input_value() in referral
                    assert risks.nth(4).input_value() not in referral
                    expect(page.locator('#saveState')).not_to_contain_text('speichere')
                    page.reload()
                    expect(prostate).to_have_value('QA Erektion')
                    expect(page.locator('[data-doctor-field="name"]')).to_have_value('QA Arzt')
                    expect(page.locator('[data-fkey="anamnese_allergien"]')).to_have_value('QA Allergie')
                    expect(page.locator('[data-checkbox-key="stuhl_rezept"]')).to_be_checked()
                    expect(risks.nth(3)).to_be_checked()
                    expect(page.locator('[data-referral-id="kardio"]')).to_have_class('referral referral-open')
                    page.locator('[data-fkey="kardio_met"]').select_option('around4')
                    expect(page.locator('[data-cardiac-result]')).to_contain_text('Kardiologische Zuweisung erforderlich')
                    expect(page.locator('[data-cardiac-result]')).not_to_contain_text('MET um 4')
                    # The EF/mMRC hint sits directly below the two fields, above the acute question.
                    field('kardio_ef').fill('45')
                    flag = page.locator('.item[data-id="t1:kardio"] .flag-box.show')
                    expect(flag).to_contain_text('EF <50%')
                    assert flag.evaluate("(el) => !!(el.compareDocumentPosition(document.querySelector('[data-fkey=\"kardio_akut\"]')) & Node.DOCUMENT_POSITION_FOLLOWING)")
                    page.locator('[data-fkey="stuhl_obstipation"]').select_option('Unbekannt')
                    expect(page.locator('[data-bowel-result]')).to_contain_text('keine Dosierung ausgewählt')
                    # A correction in another browser tab updates the open form.
                    expect(page.locator('#saveState')).not_to_contain_text('speichere')
                    editor=browser.new_page()
                    editor.goto(origin+'/?edit=BROWSER-QA')
                    editor.locator('#newPatientSex').select_option('female')
                    editor.locator('#savePatient').click()
                    expect(editor.locator('#patientModal')).not_to_have_class('modal-backdrop open')
                    page.bring_to_front()
                    expect(prostate).to_be_hidden(timeout=15000)
                    editor.goto(origin+'/?edit=BROWSER-QA')
                    editor.locator('#newPatientSex').select_option('male')
                    editor.locator('#savePatient').click()
                    expect(editor.locator('#patientModal')).not_to_have_class('modal-backdrop open')
                    page.bring_to_front()
                    expect(prostate).to_be_visible(timeout=15000)
                    expect(prostate).to_have_value('QA Erektion')
                    editor.close()
                    for width in (1280, 768, 390, 320):
                        page.set_viewport_size({'width':width, 'height':900})
                        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), f'Overflow at {width}px'
                        if os.getenv('BENE_QA_SCREENSHOTS'):
                            target = Path(os.environ['BENE_QA_SCREENSHOTS'])
                            target.mkdir(parents=True, exist_ok=True)
                            page.screenshot(path=str(target/f'clinical-{width}.png'), full_page=True)
                            page.locator('.chart-strip').screenshot(path=str(target/f'patient-header-{width}.png'))
                            for section in ('untersuchung', 'anamnese-aerzte', 'kardio', 'stuhlregulation'):
                                page.locator(f'.item[data-id="t1:{section}"]').screenshot(path=str(target/f'{section}-{width}.png'))
                    assert not errors, errors
                    browser.close()
                print('Browser QA passed: sidebar, filters, archive, CSV download, restore, modal, patient data, screenings and responsive layouts.')
            finally:
                server.terminate()
                server.wait(timeout=10)
                connections.close_all()


if __name__ == '__main__':
    main()
