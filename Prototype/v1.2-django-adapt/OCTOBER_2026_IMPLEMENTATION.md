# BENE-Erweiterungen Oktober 2026

Erweiterungen für Untersuchung, Anamnese, Stuhlregulation und kardiologisches
Assessment. Spätere Anpassungen (Patientenerfassung vom 1. November 2026,
Meeting vom 13. November 2026) sind in `README.md` beschrieben.

## Integration und Datenhaltung

Fachliche Grundlage ist `Projektunterlagen/Grundlagen/Ergaenzung_Oktober/BENE
Ergänzungen Oktober 2026.docx`. Checklistenstruktur, Felder und Texte kommen aus
`apps/checklist/definition.json`; die Engine validiert und berechnet Fortschritt, Scores, Hinweise und Arbeitsliste serverseitig. Es gibt
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
| Untersuchung | `untersuchung_abdomen`, `untersuchung_haut`, `untersuchung_hals`, `untersuchung_bauch` (`untersuchung_prostata` und `untersuchung_sturz` am 13.11.2026 entfernt) |
| Ärzte | `anamnese_urologe`, `anamnese_hausarzt`, `anamnese_aerzte` (Liste mit `specialty` und `name`) |
| Alltag / Ausscheidung | `anamnese_sozial`, `anamnese_miktion`, `anamnese_stuhl`, `anamnese_gewichtsverlust`, `anamnese_erektion`, `anamnese_shim` |
| Risiken / Status | `anamnese_allergien`, `anamnese_blutung`, `anamnese_blutung_notiz`, `anamnese_thrombose`, `anamnese_thrombose_notiz`, `anamnese_rea_ips`, `anamnese_grippe`, `anamnese_covid`, `anamnese_cyclokapron` |
| Stuhlregulation | `stuhl_obstipation`, `stuhl_rezept` |
| Kardiologie | `kardio_akut`, `kardio_kategorien`, `kardio_bemerkung`, `kardio_met`, `kardio_risiken`, `kardio_risiken_beurteilt` |

Der männliche Patientenkontext verwendet ausschliesslich `Patient.sex`.
Das Geschlecht wird zentral im bestehenden Erfassungs-/Bearbeitungsmodal gepflegt.
STOP-BANG zeigt die daraus abgeleitete Antwort schreibgeschützt an. Die bisherige
Antwort `stopbang_sex` bleibt als Altwert gespeichert, steuert aber weder die
Sichtbarkeit noch den aktuellen Score. Unbekannter Kontext blendet die
männlichen Felder aus. Ein Kontextwechsel löscht erfasste Werte nicht.
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

## Oberfläche und Validierung

Neue Bausteine im vorhandenen Formularrenderer: mehrzeilige Texte, Checkboxen,
Mehrfachauswahlen und wiederholbare Ärztelisten. Alle verwenden die bestehenden
Feld-/Listenstile. Die Stuhlregulation und das kardiale Assessment zeigen
serverseitig berechnete Ergebnisse mit klinischen Prüfhinweisen an. Ein neuer
Konsilhinweis wird ausserdem in die vorhandene Kardiologie-Arbeitsliste integriert;
es wird kein Konsil automatisch versandt oder angeordnet.

Zahlenbereiche, Schritte und Auswahllisten werden im Browser und Backend geprüft.
Umfänge und Vitalparameter haben Plausibilitätsgrenzen (siehe `README.md`), SHIM wird als extern erhobener Wert von
0–25 erfasst; es wird kein SHIM-Fragebogen oder Schweregrad abgeleitet. Freitext
ist auf 2000 Zeichen begrenzt. Ärztelisten erlauben höchstens 50 Einträge und
verlangen bei begonnenen Einträgen sowohl Fachrichtung als auch Name. Doppelte
oder unbekannte Mehrfachauswahlen sind ungültig. Nicht endliche Zahlen werden
abgewiesen. Fehler neuer ausgefüllter Felder erscheinen auch vor dem Abhaken.

Unvollständige Entwürfe bleiben speicherbar, mit `validationErrors` für fehlende
Abschlussangaben. Neue technisch ungültige Werte werden nun mit HTTP 422 und
Feldfehlern zurückgewiesen und bleiben im Browser korrigierbar. Unveränderte
ungültige Bestandswerte bleiben erhalten; Änderungen anderer Felder sind weiterhin
möglich. Behandelnde Ärzte sind optional. Im kardialen Assessment sind mMRC,
Akutstatus, MET und die explizite Bestätigung der Risikofaktorenprüfung
erforderlich; EF ist optional.
Ungeklärte oder widersprüchliche Assessmentangaben verhindern dessen Abschluss,
ohne einen bereits begründeten Warnhinweis auszublenden.

Änderungen an Antwortfeldern erzeugen `checklist_answers_changed` im bestehenden
Audit-Trail, mit Feldschlüsseln und Revision, ohne Antwortinhalte. Die bestehenden
CSRF- und Revisionsmechanismen bleiben aktiv. Frontend/API haben gemäss
Projektentscheid kein Login-/Rollensystem und keinen benutzerbezogenen Audit-Trail.

## Kardiale Screeninglogik

`CardiacScreeningConfig` und `CARDIAC_SCREENING` in `rules.py` halten die fachlich
prüfbare Konfiguration. Gemäss Meeting vom 13. November 2026 lösen **mindestens
drei** ausgewählte Risikofaktoren die Konsilempfehlung aus, und «MET um 4» hat
dieselben Konsequenzen wie «MET > 4». `derived.cardiac` enthält Status, Anzahl
ausgewählter Faktoren, Vollständigkeit der Faktorenprüfung, Begründungen und offene Abklärungen.

| Eingaben | Ergebnis aus den neuen Regeln |
| --- | --- |
| Akutstatus Ja oder mindestens eine positive akute Kategorie | Konsilhinweis |
| MET <4 | Konsilhinweis |
| Mindestens 3 gültige Risikofaktoren | Konsilhinweis |
| MET >4 oder um 4, Akutstatus Nein, höchstens 2 Faktoren, Faktoren vollständig geprüft | Keine automatische Empfehlung aus diesen Regeln |
| MET nicht beurteilbar, fehlende oder ungültige Angaben | Abklärung erforderlich; keine Entwarnung |
| Positive Kategorie mit Akutstatus Nein/Unbekannt | Konsilhinweis bleibt sichtbar, Widerspruch wird zusätzlich ausgewiesen |

Eine unabhängig positive Akutkategorie löst weiterhin den Hinweis aus. Auch ein
positiver Hinweis kann mit offenen Abklärungen einhergehen. Nicht angekreuzte
Risikofaktoren gelten erst mit «vollständig überprüft: Ja» als beurteilt.
Die fünf Checkboxen werden gezählt; es wird kein vollständiger RCRI-Score behauptet.
Die EF-/mMRC-Regel (EF <50 % oder mMRC Grad 3/4) zeigt unabhängig davon eine
Zuweisung in der Arbeitsliste an; ihr Hinweis erscheint direkt unter EF und mMRC.
Ergebnisse werden aus den gespeicherten Antworten bei jedem Laden/Speichern neu
berechnet.

## Stuhlregulation

`derived.bowel` zeigt die bereitgestellten Vorgaben ausschliesslich zur fachlichen
Prüfung: Beginn drei Tage präoperativ, bei Nein 1 Beutel Movicol morgens, bei Ja
2 Beutel morgens, keine Einnahme am OP-Tag. Bei Unbekannt/fehlender Angabe wird
keine Dosierung ausgewählt. Der Beginn wird aus dem vorhandenen OP-Datum berechnet
(ISO- und bestehendes deutsches Datumsformat); ohne gültiges Datum bleibt er offen.
Die Checkbox dokumentiert die Rezeptabgabe und Erläuterung separat und persistent.

## Offene fachliche und technische Punkte

- Das Flussdiagramm setzt hohes OP-Risiko voraus; hierfür gibt es keinen
  eigenen Entscheidungszweig.
- Für REA/IPS fehlt eine strukturierte Klassifikation; der Status wird als
  dokumentierter Wortlaut erfasst.
- Blutungs- und Thromboserisiko werden vom Fachteam noch geprüft.
- CAVE ist technisch nicht angebunden. Allergien werden ausdrücklich manuell
  abgeglichen. Eine leere Angabe wird nicht als Allergiefreiheit interpretiert.
- Das Geschlecht wird jetzt zentral in den Patientenstammdaten gepflegt. Die
  Sichtbarkeit ist keine Aussage über vorhandene Organe oder individuelle
  Behandlungsbedürfnisse. Bestehende Patienten bleiben bis zur Nachpflege unbekannt.
- Es gibt keinen technischen ärztlichen Freigabestatus oder klinischen Login im
  bisherigen Projekt. Benutzerspezifische Autorisierung und nachvollziehbare
  medizinische Freigaben bleiben wie zuvor offene Anforderungen für den
  Produktiveinsatz. Hinweise und Arbeitslisteneinträge ersetzen keine Fachprüfung.
- Die Movicol-Vorgaben sind wortgetreu aus der fachlichen Vorlage übernommen
  und müssen klinisch freigegeben werden.

Deployment im bestehenden Prozess: `python manage.py migrate`, danach
`python manage.py collectstatic --noinput` und den Applikationsdienst neu starten.
