import json
import re
import unittest
from pathlib import Path
from .mapping import LAB_CATALOG, match_lab_label, normalize_import_unit
from .parser import Word, normalize_numeric, parse_positioned_words


def report(rows, scale=1):
    words = [Word("Entnahmedatum:",140,50,270,60),Word("01.08.2026",280,50,345,60),Word("11:30",350,50,385,60),
             Word("Befunddatum:",470,50,560,60),Word("02.08.2026",620,50,685,60),Word("15:00",690,50,725,60)]
    for text,left,right in [("Untersuchungen",140,280),("Flag",370,400),("Resultat",560,610),("Einheit",620,670),("Referenzbereich",750,850)]:
        words.append(Word(text,left,100,right,110))
    for i,(label,value,unit,reference) in enumerate(rows):
        y=140+i*22
        words.append(Word(label,140,y,330,y+10))
        if value: words.append(Word(value,580,y,610,y+10))
        if unit: words.append(Word(unit,620,y,705,y+10))
        words.append(Word(reference,780,y,850,y+10))
    return [Word(w.text,w.x0*scale,w.y0*scale,w.x1*scale,w.y1*scale,w.confidence) for w in words]


class ParserTests(unittest.TestCase):
    def parse(self,rows,scale=1,method="pdf_text"):
        return parse_positioned_words(report(rows,scale),page=1,width=1000*scale,method=method)

    def test_only_exact_aliases(self):
        self.assertEqual(match_lab_label("Hämoglobin")["id"],"hb")
        for text in ["Mittleres Thrombozytenvolumen", "Hämatokrit", "eGFR", "NT-proBNP", "Troponin I", "Albumin im Urin", "Unreife Granulozyten", "Anderer Wert"]:
            self.assertIsNone(match_lab_label(text),text)

    def test_frontend_catalog_matches_backend(self):
        source=(Path(__file__).resolve().parents[3]/"eras/static/eras/js/checklist.js").read_text()
        options=json.loads(re.search(r"const LAB_OPTIONS = (\[.*?\]);",source,re.S).group(1))
        self.assertEqual(options,[x["label"] for x in LAB_CATALOG])

    def test_sample_values_and_exclusions_at_different_scales(self):
        rows=[("Hämoglobin","124","g/l","123-158"),("Thrombozyten","465","G/l","150-400"),
              ("Leukozyten","10.19","G/l","3.0-9.6"),("Kreatinin","83","µmol/l","44-80"),
              ("Kalium","5.2","mmol/l","3.5-5.1"),("Natrium","137","mmol/l","136-145"),
              ("CRP","18","mg/l","<5"),("eGFR","70","ml/min/1.7m²",">90"),
              ("Hämatokrit","0.368","l/l","0.370-0.470"),("Mittleres Thrombozytenvolumen","8.1","fl","7.2-11.1")]
        for scale in [.6,1,2.6]:
            result=self.parse(rows,scale)
            self.assertTrue(result["layoutRecognized"])
            self.assertEqual(result["measurementTimes"],["2026-08-01T11:30"])
            self.assertEqual([(v["normalizedValue"],v["normalizedUnit"]) for v in result["suggestions"]],[(r[1],r[2]) for r in rows[:7]])
            self.assertEqual(len(result["suggestions"]),7)

    def test_reference_never_fills_missing_result(self):
        v=self.parse([("CRP","","mg/l","<5")])["suggestions"][0]
        self.assertEqual(v["normalizedValue"],"")
        self.assertEqual(v["status"],"review")

    def test_operator_comma_and_ambiguous_cell(self):
        self.assertEqual(normalize_numeric("< 5,2"),("<","5.2"))
        v=self.parse([("CRP","< 5,2","mg/l","<5")])["suggestions"][0]
        self.assertEqual((v["comparisonOperator"],v["normalizedValue"]),("<","5.2"))
        self.assertEqual(self.parse([("CRP","18 19","mg/l","<5")])["suggestions"][0]["normalizedValue"],"")

    def test_units_never_guessed_or_case_folded(self):
        for raw in ["", "pmol/l", "mol/l"]:
            self.assertEqual(normalize_import_unit(raw,"kreatinin"),"")
        self.assertEqual(normalize_import_unit("g/l","thrombozyten"),"")
        self.assertEqual(normalize_import_unit("Gil","thrombozyten",ocr=True),"G/l")
        self.assertEqual(normalize_import_unit("gil","hb",ocr=True),"g/l")
        self.assertEqual(normalize_import_unit("umol/L","kreatinin"),"µmol/l")

    def test_ocr_requires_review(self):
        v=self.parse([("CRP","18","mg/l","<5")],method="ocr")["suggestions"][0]
        self.assertEqual(v["status"],"review")

    def test_old_or_missing_headers_rejected(self):
        words=report([("CRP","18","mg/l","<5")])
        words=[w for w in words if w.text!="Resultat"]
        result=parse_positioned_words(words,page=1,width=1000,method="pdf_text")
        self.assertFalse(result["layoutRecognized"])
        self.assertEqual(result["suggestions"],[])

    def test_missing_sample_time_does_not_use_report_date(self):
        words=[w for w in report([("CRP","18","mg/l","<5")]) if w.text!="Entnahmedatum:"]
        result=parse_positioned_words(words,page=1,width=1000,method="pdf_text")
        self.assertEqual(result["measurementTimes"],[])
        self.assertIsNone(result["suggestions"][0]["measurementAt"])
