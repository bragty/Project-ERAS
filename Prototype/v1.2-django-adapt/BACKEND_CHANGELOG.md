# Backend-Änderungen gegenüber dem hochgeladenen Stand

## Nicht verändert

- HTML-Struktur
- CSS / visuelles Design
- bestehende Checklisteninhalte und deren Darstellung
- bestehende Meeting-/Fragebogenlogik für unmittelbares UI-Feedback

## Neu im Backend

- relationale Modelle `Patient` und `TreatmentCase`
- fallbezogener `ChecklistState` in der Datenbank
- serverseitige Validierung der Checklistenfelder
- serverseitige Neuberechnung von G8, STOP-BANG und Epworth
- serverseitige Berechnung von BMI, Flags, Referral-Indikationen und Fortschritt
- serverseitige Archivierungsregel
- technischer Audit-Trail ohne Benutzeridentität
- REST-artige JSON-API
- SQLite lokal, optional PostgreSQL über Umgebungsvariablen

## Minimale Frontend-Integration

Nur die Datenzugriffe wurden angepasst:

- `frontpage.js`: Patient/Fall laden, suchen, erfassen, öffnen, archivieren via API
- `main.js`: fallbezogene Checklisten-Speicherung ausschliesslich via API; kein fallbezogenes localStorage mehr
- `meeting.js`: lokale Case-Summary-Persistenz entfernt; Progress/Complete kommen vom Backend

Kein HTML- oder CSS-Design wurde verändert.

## Kein User-/Login-System

Folgende Django-Komponenten wurden bewusst entfernt bzw. nicht eingebunden:

- Admin
- Auth
- Sessions
- Messages
- Login/Logout
- Rollen/Berechtigungen
- User-FKs in Audit oder fachlichen Modellen

## Laborimport (PDF / PNG / JPEG)

Neu hinzugefügt:

- fallbezogener Upload-Endpunkt `/api/cases/<fallnummer>/labs/import/`
- direkte Textextraktion aus digitalen PDFs mit `pdfplumber`
- OCR-Fallback für Scans/Bilder mit Tesseract
- PDF-Seitenrendering für OCR mit `pypdfium2`
- zentrale Labor-Mapping-Konfiguration
- Erhalt von Vergleichsoperatoren (`<`, `>`, `<=`, `>=`)
- getrennte Behandlung mehrerer Messzeitpunkte
- bearbeitbare Importvorschau vor der Übernahme
- Konflikthinweise bei bereits vorhandenen Laborwerten
- Blockierung bei eindeutig abweichender Patienten-/Fallkennung
- manuelle Bestätigung, wenn keine eindeutige Kennung erkannt werden kann
- Schutz vor doppelter Übernahme desselben Importwerts
- Import-Provenienz innerhalb der übernommenen Laborzeile (`importMeta`)
- Audit-Ereignisse `lab_import_processed` und `lab_import_confirmed` ohne
  vollständige Berichtsinhalte
- Datei-, Seiten-, Pixel- und OCR-Zeitlimits
- keine dauerhafte Speicherung hochgeladener Laborberichte

Minimale Frontend-Erweiterung nur innerhalb des bestehenden Laborpunkts:

- Drag-and-drop / Dateiauswahl
- Verarbeitungsstatus
- editierbare Vorschau
- Messzeitpunktauswahl
- Warnungen/Fundstelle
- explizite Übernahme ausgewählter Werte

Das bestehende visuelle Grunddesign und der manuelle Labor-Erfassungsweg bleiben
unverändert erhalten.
