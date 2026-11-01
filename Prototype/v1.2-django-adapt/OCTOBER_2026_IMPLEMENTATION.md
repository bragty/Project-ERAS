# BENE-Erweiterungen Oktober 2026

Implementiert und lokal geprüft am 1. November 2026.

Nachfolgende Optimierung der Patientenerfassung und Formularvalidierung:
siehe den Abschnitt vom 1. November 2026 in `README.md`. Dieser Bericht ist
entsprechend aktualisiert; vorhandene kardiale Entscheidungsregeln bleiben gleich.

## Integration und Datenhaltung

Die aktive Anwendung liegt in `Prototype/v1.2-django-adapt`. Abgeglichen wurden
ausserdem `Projektunterlagen/Grundlagen/Ergaenzung_Oktober/BENE Ergänzungen Oktober
2026.docx` einschliesslich der vier eingebetteten Tabellen-/Diagrammbilder sowie
die PDF-Gesamtübersicht im selben Ordner. Checklistenstruktur,
Felder und Texte kommen aus `apps/checklist/definition.json`; die Engine validiert
und berechnet Fortschritt, Scores, Hinweise und Arbeitsliste serverseitig. Es gibt
kein separates Untersuchungs-/Anamnesemodell und keine technische CAVE-Quelle.
Der vorhandene Abschnitt Vitalparameter wird um einen angrenzenden Abschnitt
Körperliche Untersuchung ergänzt. Bestehende Fragebögen, Raucheranamnese,
Suchtmittelliste, Laborimport und EF-/mMRC-Regeln bleiben bestehen.

Alle neuen Antworten liegen im bestehenden `ChecklistState.state.answers` des
Behandlungsfalls, der bereits mit dem Patienten verknüpft ist. Es entstehen keine
neuen Patiententabellen, Beziehungen oder API-Endpunkte. Laden und Autosave nutzen
weiterhin `/api/cases/<fallnummer>/state/`, einschliesslich Revisionsschutz und
feldweisem Browser-Merge. Verschiedene Behandlungsfälle bleiben getrennt.

Neue Antwortschlüssel:

| Bereich | Schlüssel |
| --- | --- |
| Untersuchung | `untersuchung_prostata`, `untersuchung_abdomen`, `untersuchung_haut`, `untersuchung_hals`, `untersuchung_bauch`, `untersuchung_sturz` |
| Ärzte | `anamnese_urologe`, `anamnese_hausarzt`, `anamnese_aerzte` (Liste mit `specialty` und `name`) |
| Alltag / Ausscheidung | `anamnese_sozial`, `anamnese_miktion`, `anamnese_stuhl`, `anamnese_gewichtsverlust`, `anamnese_erektion`, `anamnese_shim` |
| Risiken / Status | `anamnese_allergien`, `anamnese_blutung`, `anamnese_blutung_notiz`, `anamnese_thrombose`, `anamnese_thrombose_notiz`, `anamnese_rea_ips`, `anamnese_grippe`, `anamnese_covid`, `anamnese_cyclokapron` |
| Stuhlregulation | `stuhl_obstipation`, `stuhl_rezept` |
| Kardiologie | `kardio_akut`, `kardio_kategorien`, `kardio_bemerkung`, `kardio_met`, `kardio_risiken`, `kardio_risiken_beurteilt` |

Der männliche Patientenkontext verwendet ausschliesslich `Patient.sex`.
Das Geschlecht wird zentral im bestehenden Erfassungs-/Bearbeitungsmodal gepflegt.
STOP-BANG zeigt die daraus abgeleitete Antwort schreibgeschützt an. Die bisherige
Antwort `stopbang_sex` bleibt als Altwert gespeichert, steuert aber weder die
Sichtbarkeit noch den aktuellen Score. Unbekannter Kontext blendet die drei
optionalen männlichen Felder aus. Ein Kontextwechsel löscht erfasste Werte nicht.
Ohne zentrale Angabe bleibt der STOP-BANG-Gesamtwert unvollständig; ein zuvor
vorhandener Gesamtwert wird zusätzlich unter `legacyScores` erhalten.

Die JSON-Schemaversion steigt auf 4. Migration
`responses/0002_alter_checkliststate_schema_version.py` ändert ausschliesslich den
Modellstandardwert neuer Stände. Die anschliessende Optimierung ergänzt mit
`patients/0003_patient_sex.py` das relationale Feld `Patient.sex`, mit leerem Wert
für Bestandsdaten. Keine Datenmigration überschreibt Patientenantworten. Alte JSON-Stände
werden wie bisher beim Laden normalisiert und beim nächsten Speichern als Version
4 abgelegt. Bisher abgeschlossene Kardiologiepunkte werden bei fehlenden neuen
Assessmentangaben wieder geöffnet; vorhandene Antworten und andere gültige
Abschlussmarkierungen bleiben erhalten. Die fünf neuen Checklistenpunkte erhöhen
die Standardanzahl auf 29 präoperative und insgesamt 122 Punkte. Bestehende
Ausschlüsse pro Eingriffsart gelten weiter; neue Punkte sind standardmässig enthalten.

Die Modell-Indexnamen in `patients/models.py` und `audit/models.py` sind jetzt
explizit auf die schon vorhandenen Migrationsnamen gesetzt. Damit werden zuvor
angezeigte, unnötige Indexumbenennungen vermieden; es ändern sich keine Indizes.

## Oberfläche und Validierung

Neue Bausteine im vorhandenen Formularrenderer: mehrzeilige Texte, Checkboxen,
Mehrfachauswahlen und wiederholbare Ärztelisten. Alle verwenden die bestehenden
Feld-/Listenstile. Die Stuhlregulation und das kardiale Assessment zeigen
serverseitig berechnete Ergebnisse mit klinischen Prüfhinweisen an. Ein neuer
Konsilhinweis wird ausserdem in die vorhandene Kardiologie-Arbeitsliste integriert;
es wird kein Konsil automatisch versandt oder angeordnet.

Zahlenbereiche, Schritte und Auswahllisten werden im Browser und Backend geprüft.
Umfänge und Volumen sind nicht negativ, SHIM wird als extern erhobener Wert von
0–25 erfasst; es wird kein SHIM-Fragebogen oder Schweregrad abgeleitet. Freitext
ist auf 2000 Zeichen begrenzt. Ärztelisten erlauben höchstens 50 Einträge und
verlangen bei begonnenen Einträgen sowohl Fachrichtung als auch Name. Doppelte
oder unbekannte Mehrfachauswahlen sind ungültig. Nicht endliche Zahlen werden
abgewiesen. Fehler neuer ausgefüllter Felder erscheinen auch vor dem Abhaken.

Unvollständige Entwürfe bleiben speicherbar, mit `validationErrors` für fehlende
Abschlussangaben. Neue technisch ungültige Werte werden nun mit HTTP 422 und
Feldfehlern zurückgewiesen und bleiben im Browser korrigierbar. Unveränderte
ungültige Bestandswerte bleiben erhalten; Änderungen anderer Felder sind weiterhin
möglich. Gänzlich leere zusätzliche Anamnese-/Untersuchungsfelder sind optional,
da hierfür keine Pflichtfeldvorgaben vorliegen. Im kardialen Assessment sind
Akutstatus, MET und die explizite Bestätigung der Risikofaktorenprüfung erforderlich.
Ungeklärte oder widersprüchliche Assessmentangaben verhindern dessen Abschluss,
ohne einen bereits begründeten Warnhinweis auszublenden.

Änderungen an Antwortfeldern erzeugen `checklist_answers_changed` im bestehenden
Audit-Trail, mit Feldschlüsseln und Revision, ohne Antwortinhalte. Die bestehenden
CSRF- und Revisionsmechanismen bleiben aktiv. Frontend/API haben gemäss bisherigem
Projektentscheid kein Login-/Rollensystem und keinen benutzerbezogenen Audit-Trail;
die Erweiterung fügt keinen eigenen Freigabe- oder Berechtigungsprozess hinzu.

## Kardiale Screeninglogik

`CardiacScreeningConfig` und `CARDIAC_SCREENING` in `rules.py` halten die fachlich
prüfbare Konfiguration. Der Schwellenwert ist strikt **mehr als drei**, nicht
grösser/gleich drei. `derived.cardiac` enthält Status, Anzahl ausgewählter Faktoren,
Vollständigkeit der Faktorenprüfung, Begründungen und offene Abklärungen.

| Eingaben | Ergebnis aus den neuen Regeln |
| --- | --- |
| Akutstatus Ja oder mindestens eine positive akute Kategorie | Konsilhinweis |
| MET <4 | Konsilhinweis |
| MET >4 und 4 oder 5 gültige Risikofaktoren | Konsilhinweis |
| MET >4, Akutstatus Nein, höchstens 3 Faktoren, Faktoren vollständig geprüft | Keine automatische Empfehlung aus diesen Regeln |
| MET um 4, nicht beurteilbar, fehlende oder ungültige Angaben | Abklärung erforderlich; keine Entwarnung |
| Positive Kategorie mit Akutstatus Nein/Unbekannt | Konsilhinweis bleibt sichtbar, Widerspruch wird zusätzlich ausgewiesen |

Bei MET um 4 wird der Risikofaktor-Zweig nicht eigenständig als MET ≥4 behandelt.
Eine unabhängig positive Akutkategorie löst weiterhin den Hinweis aus. Auch ein
positiver Hinweis kann mit offenen Abklärungen einhergehen. Nicht angekreuzte
Risikofaktoren gelten erst mit «vollständig überprüft: Ja» als beurteilt.
Die fünf Checkboxen werden gezählt; es wird kein vollständiger RCRI-Score behauptet.
Die bestehenden EF-/mMRC-Regeln können unabhängig davon weiterhin eine Zuweisung
in der Arbeitsliste anzeigen. Ergebnisse werden aus den gespeicherten Antworten
bei jedem Laden/Speichern neu berechnet, entsprechend der bisherigen Architektur.

## Stuhlregulation

`derived.bowel` zeigt die bereitgestellten Vorgaben ausschliesslich zur fachlichen
Prüfung: Beginn drei Tage präoperativ, bei Nein 1 Beutel Movicol morgens, bei Ja
2 Beutel morgens, keine Einnahme am OP-Tag. Bei Unbekannt/fehlender Angabe wird
keine Dosierung ausgewählt. Der Beginn wird aus dem vorhandenen OP-Datum berechnet
(ISO- und bestehendes deutsches Datumsformat); ohne gültiges Datum bleibt er offen.
Die Checkbox dokumentiert die Rezeptabgabe und Erläuterung separat und persistent.

## Verifikation

Alle Datenbank-Schreibtests verwenden Django-Testdatenbanken bzw. die temporäre,
isolierte Datenbank des Browserskripts mit einem synthetischen QA-Fall.

| Prüfung | Ergebnis |
| --- | --- |
| `python manage.py check` | erfolgreich |
| `python manage.py makemigrations --check --dry-run` | keine ausstehenden Änderungen |
| `python manage.py test` | 98 Tests: 97 erfolgreich, 1 bestehender optionaler OCR-Test übersprungen |
| `node --check eras/static/eras/js/checklist.js` | erfolgreich |
| `node --test eras/checklist.test.cjs eras/lab-import.test.cjs eras/definition.test.cjs` | 17 erfolgreich |
| `python eras/clinical-smoke.py` | erfolgreich: echte Chromium-Bedienung, Modal-/Stammdatenkorrektur, Validierung ohne Eingabeverlust, Persistenz nach Reload, bedingte Felder, Ärzteliste, Checkboxen, MET-Grenzbereich, Stuhlregulation, 1280/768/390/320 px ohne horizontalen Überlauf |
| `collectstatic --noinput` mit temporärem `STATIC_ROOT` | 136 Dateien erfolgreich gesammelt |
| `git diff --check` | erfolgreich |

Ein separater Linter oder Frontend-Build ist im Repository nicht konfiguriert.
Die Browserprüfung setzt optional `pip install playwright` und
`python -m playwright install chromium` voraus; diese Testwerkzeuge werden nicht
als Laufzeitabhängigkeit ergänzt. Screenshots können mit `BENE_QA_SCREENSHOTS`
in einem lokalen Zielordner erzeugt werden. Der vorhandene OCR-Integrationstest
benötigt weiterhin `LAB_IMPORT_SAMPLE_PDF` und Tesseract. Eine lokale Warnung über
den nicht vorhandenen Produktivordner `staticfiles` beeinträchtigt die Tests nicht;
das getrennte Sammeln der statischen Dateien wurde erfolgreich geprüft.

## Geänderte und neue Dateien

| Datei | Änderung |
| --- | --- |
| `apps/checklist/definition.json` | Schema 4, neue Felder und Gruppen, bestehende Kardiologie erweitert |
| `apps/checklist/definition_checks.py` | neue Feldtypen und Kontextmetadaten zugelassen |
| `apps/checklist/engine.py` | strukturierte Validierung, kontextabhängige Felder, abgeleitete Ergebnisse |
| `apps/checklist/rules.py` | konfigurierbare kardiale Regeln, Stuhlregulationsinformation, Arbeitslistenintegration |
| `apps/checklist/tests_extensions.py` (neu) | Persistenz-/Validierungs-/Regressionsprüfungen, 360 Entscheidungskombinationen |
| `apps/responses/services.py` | Audit-Ereignisse bei Antwortänderungen |
| `apps/responses/tests.py` | erwartete Checklistenanzahl aktualisiert |
| `apps/responses/migrations/0002_alter_checkliststate_schema_version.py` (neu) | Standardversion neuer Stände auf 4 |
| `apps/patients/models.py`, `apps/audit/models.py` | vorhandene Indexnamen stabilisiert |
| `eras/static/eras/js/checklist.js` | Formularbausteine, bedingte Anzeige, Ergebnisdarstellung, Eingabe-/Merge-Integration |
| `eras/static/eras/css/checklist.css` | Formular-, Listen- und Warnhinweisstile, mobiles Layout |
| `eras/checklist.test.cjs` | zusätzliche Render-/Wiederherstellungs-/Fehleranzeigetests |
| `eras/clinical-smoke.py` (neu) | reproduzierbare Browserprüfung mit temporärer Datenbank |
| `README.md` | Verweis auf diesen Bericht |
| `OCTOBER_2026_IMPLEMENTATION.md` (neu) | technische Zusammenfassung und offene Fragen |

## Offene fachliche und technische Punkte

- MET um 4 ist fachlich keiner definitiven Entscheidungsseite zugeordnet. Bis zur
  Klärung bleibt dieser Zweig abklärungsbedürftig. Die MET-Tabelle nennt zwei
  Stockwerke bei 4 MET; die separate Auswahl bezeichnet sie als «MET um 4».
- **Widerspruch im Originaldokument:** Das eingebettete Flussdiagramm verzweigt
  bei «≥3» Faktoren zum Konsil, der Fliesstext und der ausdrückliche aktuelle
  Implementierungsauftrag nennen «mehr als 3». Implementiert ist entsprechend dem
  Auftrag strikt >3. Exakt drei Faktoren lösen aus diesem Zweig keine automatische
  Empfehlung aus. Diese Abweichung muss vor klinischer Freigabe geklärt werden.
  Das Diagramm setzt ausserdem hohes OP-Risiko voraus; hierfür wurde mangels
  entsprechender Vorgabe im Auftrag kein zusätzlicher Entscheidungszweig ergänzt.
- Für Sturzgefahr und REA/IPS fehlt im aktiven Code eine bestehende strukturierte
  Klassifikation. Beide werden zunächst als dokumentierter Wortlaut erfasst;
  eine verbindliche Auswahl muss fachlich bereitgestellt werden.
- CAVE ist technisch nicht angebunden. Allergien werden ausdrücklich manuell
  abgeglichen. Eine leere Angabe wird nicht als Allergiefreiheit interpretiert.
- Das Geschlecht wird jetzt zentral in den Patientenstammdaten gepflegt. Die
  Sichtbarkeit ist keine Aussage über vorhandene Organe oder individuelle
  Behandlungsbedürfnisse. Bestehende Patienten bleiben bis zur Nachpflege unbekannt.
- Es gibt keinen technischen ärztlichen Freigabestatus oder klinischen Login im
  bisherigen Projekt. Benutzerspezifische Autorisierung und nachvollziehbare
  medizinische Freigaben bleiben wie zuvor offene Anforderungen für den
  Produktiveinsatz. Hinweise und Arbeitslisteneinträge ersetzen keine Fachprüfung.
- Die Movicol-Vorgaben sind wortgetreu aus dem Auftrag umgesetzt und müssen
  klinisch freigegeben werden; es wurde kein Verordnungsdienst ergänzt.

Deployment im bestehenden Prozess: `python manage.py migrate`, danach
`python manage.py collectstatic --noinput` und den Applikationsdienst neu starten.
Es wurde kein Deployment und keine Änderung produktiver Patientendaten vorgenommen.
