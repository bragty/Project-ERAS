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
