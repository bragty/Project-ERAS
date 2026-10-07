# ERAS Django Prototype – Backend integriert, ohne Login

Diese Version basiert auf dem hochgeladenen Stand `Project-ERAS-frontend_thiago`.
Das bestehende Frontend-Design (HTML/CSS) wurde **nicht verändert**. Nur die
JavaScript-Datenzugriffe wurden dort angepasst, wo die Oberfläche mit dem neuen
Django-Backend kommunizieren muss.

## Was jetzt serverseitig ist

- Patienten und Behandlungsfälle werden in der Django-Datenbank gespeichert.
- Die Patientenübersicht lädt/sucht Fälle über eine REST-artige JSON-API.
- Das Erfassen eines Patienten/Falls erfolgt über die API.
- Beim Öffnen eines Patienten wird der Fall zuerst über die API aufgelöst.
- Der vollständige Checklistenstatus pro Fall wird serverseitig gespeichert.
- Fortschritt und `complete` werden **im Backend neu berechnet** und nicht vom Browser übernommen.
- Serverseitige Validierung prüft Feldtypen, Zahlenbereiche, Auswahllisten,
  Pflichtfelder, bedingte Pflichtfelder und Laborzeilen.
- G8-, STOP-BANG- und Epworth-Scores werden serverseitig aus den Einzelantworten neu berechnet.
- BMI, Flags und notwendige Zuweisungen werden serverseitig als abgeleitete Werte berechnet.
- Archivieren ist serverseitig nur möglich, wenn die komplette Checkliste abgeschlossen ist.
- Änderungen werden technisch/fachlich in `AuditEvent` protokolliert – **ohne Benutzeridentität**.

## Bewusst nicht vorhanden

Das Projekt hat entsprechend dem Projektentscheid **kein Login- und kein User-System**:

- keine eigene `accounts`-App
- kein Login/Logout
- keine Rollen/Berechtigungen
- kein Django Admin
- keine `django.contrib.auth`, Sessions oder Messages
- keine User-Foreign-Keys in Antworten/Audit

Wichtig: Weil keine Benutzeridentifikation existiert, kann der Audit-Trail nur
festhalten **was** und **wann** geändert wurde, aber nicht **wer** die Änderung
vorgenommen hat.

## Architektur

```text
Browser (bestehendes HTML/CSS/JS)
        |
        | JSON / Fetch API
        v
Django API Views
        |
        +--> patients/services.py
        +--> checklist/engine.py     (Validierung / Scores / Progress / Regeln)
        +--> responses/services.py    (Persistenz Checklistenstatus)
        +--> workflow/services.py     (Archivieren / Wiederherstellen)
        +--> audit/services.py
        |
        v
Django ORM
        |
        v
SQLite (lokal) oder PostgreSQL (per Umgebungsvariablen)
```

## Backend-Struktur

```text
apps/
├── core/          API-Helfer und gemeinsame Fehlerbehandlung
├── patients/      Patient + TreatmentCase, Services, Selektoren, API
├── checklist/    serverseitiges Schema + Domain Engine für Validierung/Progress
├── responses/     ChecklistState pro Behandlungsfall
├── workflow/      Archivieren / Wiederherstellen
└── audit/         AuditEvent ohne Benutzerbezug

api/
└── urls.py        zentrale API-Routen

eras/
└── ...            bestehende Presentation-Schicht / Frontend
```

## API

| Methode | Endpoint | Zweck |
|---|---|---|
| GET | `/api/health/` | Healthcheck |
| GET | `/api/patients/?q=&archived=false` | Patienten/Fälle suchen |
| POST | `/api/patients/` | Patient + Behandlungsfall erfassen |
| GET | `/api/cases/<fallnummer>/` | Fall laden |
| GET | `/api/cases/<fallnummer>/state/` | Checklistenstatus laden |
| PUT | `/api/cases/<fallnummer>/state/` | Checklistenstatus autospeichern |
| DELETE | `/api/cases/<fallnummer>/state/` | Checklistenstatus zurücksetzen |
| POST | `/api/cases/<fallnummer>/archive/` | Fall archivieren |
| POST | `/api/cases/<fallnummer>/restore/` | Archivierten Fall wiederherstellen |
| GET | `/api/checklist/schema/` | aktuelle Backend-Schema-Metadaten |

Schreibende API-Aufrufe sind nicht login-geschützt, aber weiterhin durch Djangos
CSRF-Middleware gegen Cross-Site-Requests geschützt.

## Lokal starten

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Dann:

- Patientenübersicht: `http://127.0.0.1:8000/`
- Checkliste: `http://127.0.0.1:8000/checklist/`
- Healthcheck: `http://127.0.0.1:8000/api/health/`

## Datenbank

Ohne weitere Konfiguration wird SQLite (`db.sqlite3`) verwendet.

Für PostgreSQL werden die Umgebungsvariablen `POSTGRES_DB`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `POSTGRES_HOST` und `POSTGRES_PORT` verwendet. Sobald
`POSTGRES_DB` gesetzt ist, wechselt Django automatisch auf PostgreSQL.

## Nach `git pull` auf der VM

```bash
cd /pfad/zum/projekt
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
sudo systemctl restart eras
```

Nginx und systemd müssen für diese Codeänderung nicht neu entworfen werden; sie
können weiterhin auf Django unter `127.0.0.1:8000` zeigen.

## Tests

```bash
python manage.py check
python manage.py migrate
python manage.py test
node --test eras/meeting.test.cjs
```

## Wichtige Hinweise

1. Bestehende Patientendaten aus `localStorage` werden nicht automatisch migriert.
   Ab dieser Version sind neu erfasste Patienten und fallbezogene Checklisten in
   der Serverdatenbank die massgebliche Quelle.
2. Eine Checkliste ist immer einem Behandlungsfall zugeordnet. `/checklist/`
   ohne `?case=...` wird deshalb auf die Patientenübersicht zurückgeleitet;
   es gibt keine fallbezogene Speicherung mehr in `localStorage`.
3. Der öffentliche Prototyp sollte ohne Login ausschliesslich mit fiktiven bzw.
   freigegebenen Testdaten betrieben werden.
4. Die Checklistenstruktur wird im bestehenden Frontend weiterhin gerendert; das
   Backend spiegelt die aktuelle Version für Validierung und Progress wider.
   Wenn Fragen strukturell geändert werden, müssen Frontend-Schema und
   `apps/checklist/schema.py` gemeinsam versioniert werden.
