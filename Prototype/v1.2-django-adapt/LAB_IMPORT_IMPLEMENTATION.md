# Laborbericht-Import

## Ziel und Format

Der Import unterstützt genau das Tabellenlayout des bereitgestellten Beispiel Labor.pdf:
Untersuchungen | Flag | Resultat | Einheit | Referenzbereich.
Die Beispieldatei enthält eine Bildseite ohne nutzbaren PDF-Text. OCR ist erforderlich.
Der Import arbeitet mit einem regelbasierten Vorlagenparser.
Es werden keine Ergebnisse, Befundnummern oder Daten des Beispiels im Produktivparser fest verdrahtet.

Das Layout wird anhand aller fünf Spaltenüberschriften und ihrer Reihenfolge erkannt.
Koordinaten werden relativ zur Seitenbreite ausgewertet; Datenzeilen dürfen sich verschieben.
Messzeitpunkte (Entnahme-, Befund- oder Eingangsdatum) werden weder gelesen noch gespeichert.
Die Vorschau vergleicht jeden erkannten Wert mit der aktuellen Checkliste (nach Inhalt,
nicht nach Datei): Identische Werte (gleicher Wert und gleiche Einheit) erscheinen nur in
der zusammengefassten Liste «bereits identisch erfasst». Weicht der erfasste Wert ab, wird
er angezeigt und der Berichtswert bleibt auswählbar; beim Übernehmen muss das Ersetzen
(alter → neuer Wert) ausdrücklich bestätigt werden.
Verlaufstabellen, fremde Layouts und unstrukturierte Text-PDFs werden nicht mehr importiert.
Seiten ohne erkannte Tabelle erhalten einen Hinweis. Erkannte Seiten eines mehrseitigen
Berichts können weiterhin als Vorschläge erscheinen.

## Geprüftes Ergebnis des Original-PDFs

| Auswahl | Wert | Einheit |
|---|---:|---|
| Hämoglobin | 124 | g/l |
| Hämatokrit | 0.368 | l/l |
| Thrombozyten | 465 | G/l |
| Leukozyten | 10.19 | G/l |
| Kreatinin | 83 | µmol/l |
| Kalium | 5.2 | mmol/l |
| Natrium | 137 | mmol/l |
| eGFR | 70 | ml/min/1.7m² |
| CRP | 18 | mg/l |

Diese Sollwerte stehen ausschliesslich in Tests.
Die weiteren 17 Untersuchungszeilen werden nicht vorgeschlagen, darunter
Erythrozyten, MCV/MCH/MCHC, Differenzialblutbild und MPV.
Nicht enthaltene auswählbare Untersuchungen wie Ferritin werden nicht ergänzt.

## Rote (auffällige) Resultate

KISIM druckt auffällige Resultate rot. In Graustufen werden sie mittelgrau, und die
OCR verliert oder erfindet den Dezimalpunkt (HbA1c 8.9 wurde als 89 gelesen).
Resultat-Zellen mit roter Schrift werden deshalb aus dem Farbbild zweimal neu gelesen
(Grünkanal und Luminanz, binarisiert, nur Ziffern und < > . , ( )). Der Wert wird nur
übernommen, wenn alle Lesungen mit Zahl übereinstimmen; sonst bleibt das Resultat leer
und muss manuell erfasst werden. Fussnotenverweise wie «92 (1)» gehören nicht zum Wert.
Geprüft an allen zehn roten Werten des Beispiel-PDFs und des KISIM-Screenshots.

## Zuordnung und Einheiten

`mapping.py` enthält den Dropdown-Katalog und explizite Synonyme. Die angezeigten
Bezeichnungen sind die exakten KISIM-Namen (z. B. Hämoglobin, Prothrombinzeit (Quick),
Troponin-T high sensitive). BNP, Albumin und «Quick / INR» sind Altwerte: bestehende
Zeilen bleiben sichtbar, neu auswählen oder importieren lassen sie sich nicht.
Gespeicherte Zeilen werden mit Schema-Version 5 umbenannt (Hb → Hämoglobin,
Troponin T → Troponin-T high sensitive; Quick / INR nur bei eindeutiger Einheit).
INR hat in KISIM keine Einheit und wird mit der Einheit «INR» übernommen.
Keine Teilwortsuche und keine unscharfe Ähnlichkeitssuche: Thrombozytenvolumen
wird beispielsweise nicht zu Thrombozyten, NT-proBNP nicht zu BNP.
«Anderer Wert» ist manuell verfügbar, aber kein Ziel des Imports.

Bei Bildern korrigiert `normalize_import_unit(..., ocr=True)` belegte OCR-Verwechslungen
der Einheiten: «/l» als N, A, i, ! oder t gelesen, µ als u, y oder p (p nur, wenn pmol
für den Parameter nicht zulässig ist), «mi/» statt «ml/» und ² als ?, * oder 7. Eine
Korrektur gilt nur, wenn danach genau eine zulässige Einheit passt; bei mehreren
Möglichkeiten (z. B. Hb g/l oder g/dl) bleibt die Einheit leer. Geprüft an allen
Einheiten des Beispiel-PDFs und des KISIM-Screenshots ohne falsche Zuordnung.

`IMPORT_UNITS` definiert zulässige Einheiten pro Parameter. Es gibt keine
automatischen Einheitenumrechnungen. g/l und G/l bleiben unterschiedliche Einheiten.
OCR-Schreibweisen Gil → G/l und gil → g/l sind explizit hinterlegt; u/μ wird bei
passenden Einheiten zu µ normalisiert. pmol/l oder mol/l wird niemals geraten
oder automatisch in µmol/l umgewandelt.

Fehlende, mehrdeutige oder ungültige Resultate bleiben leer. Referenzbereiche
und Flags füllen keine fehlenden Resultate. Vergleichszeichen bleiben erhalten.
Jeder OCR-Vorschlag erhält den Prüfstatus und ist zunächst nicht ausgewählt.

## Verarbeitung und Bedienung

1. PDF/PNG/JPEG per Drag-and-drop oder Dateiauswahl hochladen.
2. Direkt lesbares PDF: pdfplumber; andernfalls PDFium-Rendering und Tesseract.
3. OCR verwendet Seitenmodus 6 und bei unklaren Einheiten einen gezielten
   zweiten Durchlauf nur für die betreffende Zelle (Modus 7).
4. Nur erkannte erlaubte Parameter gelangen in die Vorschau.
5. Parameterzuordnung ist in der Vorschau gesperrt; Wert, Einheit und Datum
   können kontrolliert und korrigiert werden.
6. Patientenzuordnung bestätigen, Werte auswählen, «Werte übernehmen».
7. Bereits vorhandene Werte werden erst nach zusätzlicher Bestätigung ersetzt.
8. Der bestehende Autosave speichert die bestätigten Formularwerte.

Der Beispielbericht enthält keine eindeutige Patienten-/Fallkennung.
Befundnummer und Auftragsnummer werden nicht als Patientenkennung behandelt.
Daher muss die Zuordnung manuell bestätigt werden.

Der Speicher-Endpunkt prüft importierte Parameter-ID, Dropdown-Bezeichnung,
Zahlenwert und Einheit serverseitig. Neue Importe enthalten zudem die Vorlagen-ID
und Quellbezeichnung, deren Zuordnung ebenfalls geprüft wird. Fehler ergeben
HTTP 422; die Transaktion speichert dabei keine Änderungen. Dies ist eine
Validierung des Importinhalts, keine kryptographische Herkunftsprüfung.

Manuelle Zeilen ohne Importmetadaten bleiben unverändert. Bei einer manuellen
Änderung eines bereits importierten Parameters muss seine Herkunft weiterhin
passen; für einen anderen Parameter eine neue manuelle Zeile anlegen.

## Installation

Im Projektordner `Prototype/v1.2-django-adapt` mit aktiviertem Python-Environment:

```bash
python -m pip install -r requirements.txt
```

Tesseract muss zusätzlich als Systemprogramm installiert und im PATH sein.
Unter Ubuntu/Debian:

```bash
sudo apt install tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng
```

Unter Windows Tesseract inklusive deutscher und englischer Sprachdaten
installieren und den Installationsordner zum PATH des ausführenden Prozesses
hinzufügen. Danach Terminal, IDE bzw. Serverdienst neu starten.

```bash
tesseract --version
tesseract --list-langs
```

Die Sprachliste muss `deu` und `eng` enthalten. Die bestehende Einstellung
`LAB_IMPORT_OCR_LANG=deu+eng` beibehalten. Bestehende Upload-, Seiten- und
Pixelgrenzen gelten weiter; das OCR-Zeitbudget gilt pro Seite einschliesslich
Zellnachlesung. Danach den Django-/WSGI-Dienst gemäss bisherigem Deployment
neu starten und gegebenenfalls `python manage.py collectstatic --noinput`
ausführen.

## Tests

```bash
python manage.py test apps.checklist apps.responses apps.patients eras
node --test eras/checklist.test.cjs eras/lab-import.test.cjs
```

Für den echten OCR-Test zusätzlich `LAB_IMPORT_SAMPLE_PDF` auf den absoluten
Pfad des bereitgestellten Beispiel-PDFs setzen. Ohne diese Variable wird nur
jener Test übersprungen. Die Originaldatei wird nicht in das Codepaket kopiert.

Linux-Beispiel:

```bash
LAB_IMPORT_SAMPLE_PDF=/pfad/zum/Beispiel-Labor.pdf python manage.py test apps.checklist
```

PowerShell-Beispiel:

```powershell
$env:LAB_IMPORT_SAMPLE_PDF = "C:\Pfad\Beispiel Labor.pdf"
python manage.py test apps.checklist
```

## Grenzen

Ein Originalbericht ist eine erfolgreiche Regression, kein Nachweis allgemeiner
OCR-Genauigkeit. Abweichende Scannerqualität und OCR-Versionen können Ergebnisse
verändern; deshalb bleiben die Sichtkontrolle und bewusste Auswahl erforderlich.
Der Prototyp enthält kein Login-/Berechtigungssystem.

## HbA1c-Beurteilung

Vorgabe: `Projektunterlagen/Grundlagen/Laborimport_Beispiel/HbA1c_Logik.png`.
Die Anamnese-Frage «Diabetes mellitus» (Ja/Nein/Unbekannt, Abschnitt «Allergien, Risiken
und klinischer Status») bestimmt die Gruppe. Die Regel steht ausschliesslich in
`rules.py` (`assess_hba1c`) und gilt für manuell erfasste und importierte Werte:

| Gruppe | HbA1c | Massnahme |
|---|---|---|
| Nicht-Diabetiker/in | < 5.7 % | Keine Massnahmen |
| Nicht-Diabetiker/in | 5.7–6.4 % | Vermerk im Austrittsbericht, Nachkontrolle bei Vd. a. Prädiabetes |
| Nicht-Diabetiker/in | > 6.4 % | Kontakt Hausarzt für Beginn antidiabetische Therapie |
| Diabetiker/in | < 8 % | Keine Massnahmen |
| Diabetiker/in | ≥ 8 % | Kontakt Hausarzt bzgl. Optimierung der antidiabetischen Therapie |
| beide | > 10 % | zusätzlich: ggf. Diabetesberatung in Rücksprache mit dem Hausarzt |

Die Vorgabe nennt «<8 %» und «>8 %»; genau 8.0 % wird der höheren Gruppe zugeordnet.
Ohne Diabetes-Status, bei anderer Einheit als % oder bei einem Vergleichswert, der keiner
Gruppe eindeutig zugeordnet werden kann (z. B. «>6.0»), erscheint ein Prüfhinweis statt
einer Massnahme. Der Hinweis erscheint unter den Laborwerten und bereits in der
Importvorschau; wird der Wert dort geändert, folgt die Beurteilung nach der Übernahme.
