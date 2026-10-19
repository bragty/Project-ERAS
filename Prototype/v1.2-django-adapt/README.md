## Serverseitig

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

Die klinische Oberfläche (Patientenübersicht, Checkliste) und die API haben
entsprechend dem Projektentscheid **kein Login- und kein User-System**:

- keine eigene `accounts`-App
- kein Login/Logout im Frontend
- keine Rollen/Berechtigungen im Frontend/API
- keine User-Foreign-Keys in Antworten/Audit

Wichtig: Weil keine Benutzeridentifikation existiert, kann der Audit-Trail nur
festhalten **was** und **wann** geändert wurde, aber nicht **wer** die Änderung
vorgenommen hat.

Ausnahme: Das **Django-Admin** (Backoffice) ist eingebunden und verwendet dafür
`django.contrib.auth`, Sessions und Messages. Es ist nur mit Admin-Konto
erreichbar; siehe Abschnitt [Django-Admin](#django-admin-backoffice).

## Django-Admin (Backoffice)

Erreichbar unter `http://127.0.0.1:8000/admin/` (Pfad über `DJANGO_ADMIN_URL`
änderbar). Einmalig ein Konto anlegen:

```bash
python manage.py migrate
python manage.py createsuperuser
```

| Bereich | Möglich | Bewusst nicht möglich |
|---|---|---|
| Patienten | suchen, Stammdaten korrigieren, Fälle des Patienten sehen | – |
| Behandlungsfälle | filtern/suchen, Stammdaten korrigieren, neu anlegen, archivieren/wiederherstellen (Aktion) | Archivieren mit unvollständiger Checkliste |
| Checklistenstände | Fortschritt, Revision, Validierungsfehler und JSON-Zustand ansehen | Antworten bearbeiten (nur über die App, damit Validierung/Revision/Audit greifen) |
| Audit-Events | filtern, suchen, Metadaten ansehen | ändern, löschen |
| Benutzer/Gruppen | Admin-Konten und Rechte verwalten | – |

Änderungen an Fällen über das Admin erzeugen `AuditEvent`s
(`case_created_admin`, `case_updated_admin`); zusätzlich führt Django ein eigenes
Admin-Protokoll mit Benutzername („Letzte Aktionen“ / Verlauf pro Objekt).

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
SQLite (Standard) oder optional PostgreSQL (per Umgebungsvariablen)
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
| PUT | `/api/cases/<fallnummer>/state/` | Checklistenstatus autospeichern (optional `baseRevision`, sonst 409 bei Konflikt) |
| GET | `/api/cases/<fallnummer>/state/revision/` | aktuelle Revision für Live-Aktualisierung |
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
- Django-Admin: `http://127.0.0.1:8000/admin/` (vorher `python manage.py createsuperuser`)

## Datenbank

Standard ist **SQLite**, lokal wie in Produktion. Die Datenbank ist eine einzelne
Datei; ein eigener DB-Server ist nicht nötig.

- Pfad: `SQLITE_PATH` (ohne Wert `db.sqlite3` im Projektordner). In Produktion
  einen eigenen Datenordner verwenden, z. B. `/opt/eras/data/db.sqlite3`. Der
  App-User braucht Schreibrechte auf den **Ordner**, weil SQLite daneben
  `-wal`/`-shm`-Dateien anlegt.
- Für mehrere Gunicorn-Worker ist SQLite auf WAL-Modus, Lock-Wartezeit
  (`SQLITE_TIMEOUT_SECONDS`, Standard 20 s) und `IMMEDIATE`-Transaktionen
  eingestellt. Das reicht für eine Station bzw. Klinik mit einem App-Server.
  Die Datei muss auf einer lokalen Platte liegen, nicht auf einem Netzlaufwerk
  (NFS/SMB).
- Backup im laufenden Betrieb (konsistente Kopie trotz WAL):

  ```bash
  sqlite3 /opt/eras/data/db.sqlite3 ".backup '/backup/eras-$(date +%F).sqlite3'"
  ```

**PostgreSQL (optional):** z. B. für eine Klinik mit vorhandener
DB-Infrastruktur oder mehreren App-Servern. Dafür `POSTGRES_DB`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `POSTGRES_HOST` und `POSTGRES_PORT` setzen und
`python manage.py migrate` ausführen. Sobald `POSTGRES_DB` gesetzt ist, wechselt
Django automatisch auf PostgreSQL; `SQLITE_PATH` wird dann ignoriert. Der
Treiber (`psycopg`) ist bereits in `requirements.txt` enthalten. Bestehende Daten
lassen sich bei Bedarf mit `dumpdata`/`loaddata` übertragen.

## Nach `git pull` auf der VM

```bash
cd /pfad/zum/projekt
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart eras
```

Nginx und systemd müssen für diese Codeänderung nicht neu entworfen werden; sie
können weiterhin auf Django unter `127.0.0.1:8000` zeigen. Statische Dateien
(CSS/JS, Admin-Design) liefert Django selbst über WhiteNoise aus; bei
`DJANGO_DEBUG=false` muss dafür vorher `collectstatic` gelaufen sein.

## Produktivbetrieb (Spital-IT)

Die Konfiguration erfolgt ausschliesslich über Umgebungsvariablen (Vorlage:
`.env.example`). Mit `DJANGO_ENV=production` gilt ein strenges Profil:

- Start bricht ab, wenn `DJANGO_SECRET_KEY` oder `DJANGO_ALLOWED_HOSTS` fehlen
  bzw. `DJANGO_DEBUG=true` gesetzt ist.
- Datenbank: SQLite unter `SQLITE_PATH`, optional PostgreSQL (siehe
  [Datenbank](#datenbank)).
- HTTPS-Härtung aktiv: Redirect auf HTTPS, sichere Cookies, HSTS, Proxy-Header.
- Statische Dateien mit Hash im Namen und langem Caching (WhiteNoise).
- Admin-Passwörter mind. 12 Zeichen, Admin-Sessions laufen nach 8 h ab.

Alle Stellen, die je nach Hosting angepasst werden müssen, sind im Code mit
`ANPASSEN (Hosting)` markiert:

```bash
grep -rn "ANPASSEN (Hosting)" --exclude-dir=.venv .
```

| Datei | Zweck |
|---|---|
| `eras_project/settings.py` | Profile, Sicherheit, DB, Logging |
| `.env.example` | alle Umgebungsvariablen |
| `deploy/gunicorn.conf.py` | Applikationsserver |
| `deploy/eras.service` | systemd-Dienst (klassischer Linux-Server) |
| `deploy/nginx-eras.conf` | Reverse-Proxy mit TLS, Upload-Limit, Admin-IP-Sperre |
| `Dockerfile`, `.dockerignore` | Container-Variante (Docker/Podman/Kubernetes) |

Deployment-Schritte pro Release:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy     # nur HSTS-Subdomain/Preload-Warnungen sind ok
sudo systemctl restart eras          # bzw. Container neu ausrollen
```

Vor dem Einsatz mit echten Patientendaten mit der Spital-IT klären:

1. **Authentifizierung für Frontend und API** (z. B. SSO über den Proxy) – aktuell
   sind diese ohne Login erreichbar. Das ist der wichtigste offene Punkt.
2. Hostname, TLS-Zertifikat und ob TLS am Proxy/Load-Balancer endet.
3. Ablageort der SQLite-Datei (bzw. PostgreSQL-Instanz), Backup- und
   Restore-Konzept, Aufbewahrungsfristen.
4. Netzbereiche, aus denen das Admin erreichbar sein darf.
5. Zentrales Logging/Monitoring (Healthcheck: `/api/health/`).
6. Tesseract-Installation auf dem Server (im Dockerfile bereits enthalten).

## Tests

```bash
python manage.py check
python manage.py migrate
python manage.py test
node --test eras/meeting.test.cjs
```

## Wichtige Hinweise

1. Der öffentliche Prototyp sollte ohne Login ausschließlich mit fiktiven bzw.
   freigegebenen Testdaten betrieben werden.
2. Die Checklistenstruktur wird im bestehenden Frontend weiterhin gerendert; das
   Backend spiegelt die aktuelle Version für Validierung und Progress wider.
   Wenn Fragen strukturell geändert werden, müssen Frontend-Schema und
   `apps/checklist/schema.py` gemeinsam versioniert werden.

## Laborbericht-Import (PDF / Bild)

Im Abschnitt **Labor (inkl. PBM)** kann zusätzlich zur manuellen Erfassung ein
Laborbericht als PDF, PNG oder JPEG verarbeitet werden. Der Import ist bewusst
zweistufig:

```text
Datei auswählen / Drag & Drop
        ↓
POST /api/cases/<fallnummer>/labs/import/
        ↓
Text-PDF: pdfplumber / Scan oder Bild: Tesseract OCR
        ↓
vorlagenbasierte Zuordnung + Warnungen
        ↓
Importvorschau im Browser
        ↓
medizinische/fachliche Kontrolle
        ↓
"Werte übernehmen"
        ↓
bestehender ChecklistState-Autosave
```

Der Upload-Endpunkt speichert die Datei **nicht dauerhaft**. Er gibt nur
strukturierte Vorschläge zurück. Erst bestätigte Werte werden über den bereits
bestehenden ChecklistState-Speicherweg persistiert.

### Import-API

| Methode | Endpoint | Zweck |
|---|---|---|
| POST | `/api/cases/<fallnummer>/labs/import/` | Laborbericht verarbeiten und Importvorschläge liefern |

Der Request ist `multipart/form-data` mit genau einem Feld `file`.
Unterstützt werden PDF, PNG und JPEG. Dateiendung und Dateiinhalt werden
gegeneinander geprüft.

### Mapping und Berichtsformat

Die zentrale Zuordnung zwischen erkannten Laborbezeichnungen und den bereits
vorhandenen Dropdown-Werten liegt in:

```text
apps/checklist/lab_import/mapping.py
```

Die Extraktionslogik liegt in:

```text
apps/checklist/lab_import/parser.py
apps/checklist/lab_import/service.py
```

Der Parser ist ausschliesslich auf die bereitgestellte Vorlage **Beispiel Labor.pdf**
ausgerichtet: Untersuchungen | Flag | Resultat | Einheit | Referenzbereich.
Der frühere Verlaufstabellen-Parser und generische Text-Fallback sind entfernt.
Es werden nur vollständige registrierte Laborbezeichnungen aus dem bestehenden
Dropdown importiert. Nicht unterstützte Untersuchungen werden ignoriert;
«Anderer Wert» bleibt ausschliesslich für die manuelle Erfassung verfügbar.

Das Beispiel ist ein Bild-PDF und benötigt Tesseract mit `deu+eng`. Unklare
Einheiten werden gezielt erneut gelesen und bleiben bei Unsicherheit leer.
Jeder OCR-Vorschlag muss kontrolliert und bewusst ausgewählt werden.
Das Entnahmedatum wird aus dem gleichnamigen Kopf-Feld gelesen; Befunddatum
und Laboreingangsdatum sind keine Messzeitpunkte.

Details, Prüfergebnisse und Änderungsübersicht: `LAB_IMPORT_IMPLEMENTATION.md`.

### Neue Python-/Systemabhängigkeiten

Python-Abhängigkeiten werden wie gewohnt installiert:

```bash
pip install -r requirements.txt
```

Für OCR muss auf Ubuntu zusätzlich Tesseract vorhanden sein:

```bash
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng
```

Prüfen:

```bash
tesseract --version
tesseract --list-langs | grep -E 'deu|eng'
```

Für digital erzeugte PDFs wird zuerst der vorhandene Text direkt gelesen. OCR
wird nur für Bilddateien bzw. PDF-Seiten verwendet, auf denen die direkte
Textextraktion keine verwertbare Labortabelle liefert.

### Konfiguration

Optionale Umgebungsvariablen:

```text
LAB_IMPORT_MAX_BYTES=10485760
LAB_IMPORT_MAX_PAGES=10
LAB_IMPORT_MAX_IMAGE_PIXELS=25000000
LAB_IMPORT_OCR_TIMEOUT_SECONDS=30
LAB_IMPORT_OCR_LANG=deu+eng
```

### Sicherheit und aktuelle Projektgrenze

- Uploads werden nur im Kontext einer existierenden Fallnummer verarbeitet.
- Schreibende Requests bleiben durch Django-CSRF geschützt.
- Temporäre PDF-Dateien werden nach der Verarbeitung entfernt.
- Gewöhnliche Logs/Audit-Einträge enthalten keine vollständigen Laborberichte.
- Der Audit-Trail protokolliert nur strukturelle Importinformationen wie Hash,
  Anzahl bestätigter Werte und interne Labor-IDs.
- Das Projekt besitzt gemäss Projektentscheid **kein Login-/User-System**.
  Deshalb ist aktuell auch keine benutzerbezogene Berechtigungsprüfung möglich.
  Für einen produktiven klinischen Einsatz muss Authentifizierung/Autorisierung
  ergänzt werden; CSRF und Fallkontext ersetzen diese nicht.

### Live-Aktualisierung bei mehreren Arbeitsplätzen

- neuer Endpoint `GET /api/cases/<fallnummer>/state/revision/` (leichtgewichtig, nur Revision + Zeitpunkt)
- `PUT /api/cases/<fallnummer>/state/` akzeptiert optional `baseRevision`; ist der Fall
  zwischenzeitlich anderswo gespeichert worden, antwortet das Backend mit `409 revision_conflict`
  statt die fremden Änderungen zu überschreiben (ohne `baseRevision` unverändertes Verhalten)
- `checklist.js`: offene Checklisten fragen alle 3 s die Revision ab und übernehmen neuere
  Serverstände per Drei-Wege-Merge feldweise; noch nicht gespeicherte lokale Eingaben bleiben
  erhalten, Fokus, Cursor, Scrollposition und geöffnete Notizen/Zuweisungen ebenfalls.
  Auf- und zugeklappte Blöcke (`openBlocks`) bleiben pro Arbeitsplatz lokal.
- `frontpage.js`: Patientenübersicht aktualisiert sich alle 5 s (nur bei Änderungen neu gerendert)
- Polling pausiert in Hintergrund-Tabs und läuft beim Zurückwechseln sofort an.
  Keine zusätzliche Infrastruktur (WebSockets/Redis) nötig; Nginx/systemd bleiben unverändert.

### Wichtige Einschränkung

Der im Repository vorhandene Beispielstand enthält einen Labor-Screenshot, aber
keinen vollständigen originalen Labor-PDF-Export mit allen benötigten Parametern.
Der OCR-Pfad wurde daher gegen den verfügbaren Screenshot und der Text-PDF-Pfad
gegen eine synthetische tabellarische PDF-Struktur geprüft. Vor einer fachlichen
Abnahme müssen anonymisierte Originalberichte (digitales PDF, Scan/Bild,
mehrseitig) mit manuell geprüften Sollwerten getestet werden.
