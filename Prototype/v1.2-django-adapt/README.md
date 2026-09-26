# Eras Django Adaptation

This directory contains a Django adaptation of the existing Eras V1.1 prototype. The original HTML files remain unchanged and were used as the source of truth for markup, styling, JavaScript behavior, and static assets.

## Folder structure

- `manage.py` - Django command entry point.
- `eras_project/` - Project settings and root URL configuration.
- `eras/` - Django app with views, routes, tests, templates, and static files.
- `eras/templates/eras/base.html` - Shared page shell with Django static loading and overridable blocks.
- `eras/templates/eras/pages/` - Page templates for the front page and checklist.
- `eras/templates/eras/includes/` - Header, footer, and modal partials extracted from the prototype.
- `eras/static/eras/css/` - Extracted CSS files.
- `eras/static/eras/js/` - Extracted JavaScript files plus a localStorage-backed storage helper.
- `eras/static/eras/images/` - Copied image assets used by the prototype.

## Setup

From this directory:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

On Windows PowerShell, activate the virtual environment with:

```powershell
.\.venv\Scripts\Activate.ps1
```

Open <http://127.0.0.1:8000/> for the patient overview and <http://127.0.0.1:8000/checklist/> for the checklist.

## Verification

Run:

```bash
python manage.py check
python manage.py migrate
python manage.py test
```

## Notes and assumptions

- No Django models were added because the source prototype is frontend-only and stores checklist state in browser storage.
- `window.storage` is polyfilled with `localStorage` so the existing autosave behavior works in a normal Django development browser session.
- The KSW logo was copied into Django static files and is referenced through `{% static %}`.
- External links from the source prototype remain external links.

## KSW review 25 September 2026

The current Django prototype implements the review from
`Protokoll_Meeting_KSW_25.09.2026.pdf` using `Grundlagen/Checkliste BENE20052026.docx`
as its content source. The older standalone HTML prototypes are historical versions.

- The questionnaires section contains collapsible, interactive G8, ECOG,
  Epworth, STOP-BANG and mMRC forms transcribed from the Word source. G8,
  Epworth and STOP-BANG sum all individual answers automatically. Previous
  manually entered totals remain visible as legacy values, without fabricating
  individual answers. The source does not contain a complete NRS form, so NRS
  retains a collapsible manual total entry.
- Checklist completion requires explicit confirmation and valid required inputs;
  substance-history contents are optional. Conditional fields are required only
  where applicable. Completed items collapse and can be reopened by unchecking.
- BMI, threshold colours, shared mMRC and pathway data, referral status, dates,
  and copyable referral texts (including physiotherapy) are available.
- Stationary postoperative section headings have individually confirmable measures.
  Removed measures no longer contribute to progress. Original pathway IDs are
  retained; previous group confirmations are not applied to individual measures.
- Cases are stored separately by case number. Fully checked cases can be archived
  from the overview, opened from the archive and restored. New patient entries persist.
  This remains a localStorage prototype, without server-side patient storage.
  The previous unassigned checklist stays at `/checklist/`; it is not silently
  assigned to a patient case.

Open items explicitly recorded by the meeting remain open:

- G8 referral threshold: requires KSW confirmation; manual referral decision is available.
- Intraoperative content: awaits clinical review.
- KISIM laboratory import/OCR and ICT integration: not implemented. Manual entry remains.
  The repository currently has no KISIM connector, import endpoint or OCR dependency.
  A feasible next step is local processing of representative, de-identified exports,
  followed by user confirmation of extracted value, unit and patient/case before import.
  Scanned images require OCR; text PDFs can use text extraction. Both need validation
  against real export formats before automatic field assignment can be trusted.

No emails, KSW submissions, or external system changes are performed by these updates.

Run the additional client logic regression tests with `node --test eras/meeting.test.cjs`.
