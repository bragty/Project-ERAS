## Neu im Backend

- relationale Modelle `Patient` und `TreatmentCase`
- fallbezogener `ChecklistState` in der Datenbank
- serverseitige Validierung der Checklistenfelder
- serverseitige Neuberechnung von G8, STOP-BANG und Epworth
- serverseitige Berechnung von BMI, Flags, Referral-Indikationen und Fortschritt
- serverseitige Archivierungsregel
- technischer Audit-Trail ohne Benutzeridentität (da keine User verlangt wurden)
- SQLite lokal, optional PostgreSQL über Umgebungsvariablen

## Minimale Frontend-Integration

Nur die Datenzugriffe wurden angepasst:

- `frontpage.js`: Patient/Fall laden, suchen, erfassen, öffnen, archivieren via API
- `main.js`: fallbezogene Checklisten-Speicherung ausschliesslich via API; kein fallbezogenes localStorage mehr
- `meeting.js`: lokale Case-Summary-Persistenz entfernt; Progress/Complete kommen vom Backend

## Kein User-/Login-System

Folgende Django-Komponenten haben wir bewusst entfernt bzw. nicht eingebunden:

- Admin
- Auth
- Sessions
- Messages
- Login/Logout
- Rollen/Berechtigungen
- User-FKs in Audit oder fachlichen Modellen
