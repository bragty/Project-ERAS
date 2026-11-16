import json
import re
import unittest
from pathlib import Path
from .mapping import LAB_CATALOG, SELECTABLE_LABELS, match_lab_label, migrate_lab_row, normalize_import_unit
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
        for text,lab_id in [("Prothrombinzeit (Quick)","quick"),("INR","inr"),("Troponin-T high sensitive","troponin_t"),
                            ("NT-proBNP","nt_probnp"),("HbAlc","hba1c"),("ASAT (GOT)","asat"),("Gamma-GT (GGT)","ggt"),("Vitamin B12","vitamin_b12")]:
            self.assertEqual(match_lab_label(text)["id"],lab_id,text)
        for text in ["Mittleres Thrombozytenvolumen", "MCHC", "Troponin I", "Albumin im Urin", "Unreife Granulozyten", "Anderer Wert", "Eisen", "Transferrin"]:
            self.assertIsNone(match_lab_label(text),text)

    def test_display_labels_are_exact_kisim_names(self):
        self.assertEqual(SELECTABLE_LABELS[:7],("Hämoglobin","Hämatokrit","Thrombozyten","Leukozyten","Prothrombinzeit (Quick)","INR","HbA1c"))
        self.assertNotIn("BNP",SELECTABLE_LABELS); self.assertNotIn("Albumin",SELECTABLE_LABELS)

    def test_legacy_parameters_are_not_imported(self):
        result=self.parse([("BNP","100","ng/l","<100"),("Albumin","40","g/l","35-52")])
        self.assertEqual(result["suggestions"],[])

    def test_inr_has_no_unit_column(self):
        v=self.parse([("INR","1.16","","")])["suggestions"][0]
        self.assertEqual((v["labLabel"],v["normalizedValue"],v["normalizedUnit"]),("INR","1.16","INR"))
        self.assertEqual(normalize_import_unit("%","inr"),"")

    def test_stored_rows_are_renamed_unambiguously(self):
        self.assertEqual(migrate_lab_row({"type":"Hb","value":"124","unit":"g/l"})["type"],"Hämoglobin")
        self.assertEqual(migrate_lab_row({"type":"Troponin T","value":"9","unit":"ng/l"})["type"],"Troponin-T high sensitive")
        self.assertEqual(migrate_lab_row({"type":"Quick / INR","value":"76","unit":"%"})["type"],"Prothrombinzeit (Quick)")
        self.assertEqual(migrate_lab_row({"type":"Quick / INR","value":"1.1","unit":"1"}),{"type":"INR","value":"1.1","unit":"INR"})
        self.assertEqual(migrate_lab_row({"type":"Quick / INR","value":"1.1","unit":""})["type"],"Quick / INR")
        imported=migrate_lab_row({"type":"Quick / INR","value":"1.1","unit":"INR","importMeta":{"labId":"quick_inr","originalLabel":"INR"}})
        self.assertEqual((imported["type"],imported["importMeta"]["labId"]),("INR","inr"))
        for label in ("BNP","Albumin","Hämoglobin"):
            row={"type":label,"value":"1","unit":"g/l"}
            self.assertEqual(migrate_lab_row(row)["type"],label if label!="Hb" else "Hämoglobin")

    def test_frontend_catalog_matches_backend(self):
        source=(Path(__file__).resolve().parents[3]/"eras/static/eras/js/checklist.js").read_text(encoding="utf-8")
        options=json.loads(re.search(r"const LAB_OPTIONS = (\[.*?\]);",source,re.S).group(1))
        self.assertEqual(options,list(SELECTABLE_LABELS))
        ids=json.loads(re.search(r"const LAB_ID_BY_LABEL = (\{.*?\});",source,re.S).group(1))
        self.assertEqual(ids,{x["label"]:x["id"] for x in LAB_CATALOG if not x.get("legacy")})
        legacy=json.loads(re.search(r"const LAB_LEGACY_OPTIONS = (\[.*?\]);",source,re.S).group(1))
        self.assertEqual(legacy,[x["label"] for x in LAB_CATALOG if x.get("legacy")])

    def test_sample_values_and_exclusions_at_different_scales(self):
        rows=[("Hämoglobin","124","g/l","123-158"),("Thrombozyten","465","G/l","150-400"),
              ("Leukozyten","10.19","G/l","3.0-9.6"),("Kreatinin","83","µmol/l","44-80"),
              ("Kalium","5.2","mmol/l","3.5-5.1"),("Natrium","137","mmol/l","136-145"),
              ("CRP","18","mg/l","<5"),("eGFR","70","ml/min/1.7m²",">90"),
              ("Hämatokrit","0.368","l/l","0.370-0.470"),("Mittleres Thrombozytenvolumen","8.1","fl","7.2-11.1")]
        for scale in [.6,1,2.6]:
            result=self.parse(rows,scale)
            self.assertTrue(result["layoutRecognized"])
            self.assertEqual([(v["normalizedValue"],v["normalizedUnit"]) for v in result["suggestions"]],[(r[1],r[2]) for r in rows[:9]])
            self.assertEqual(result["suggestions"][0]["labLabel"],"Hämoglobin")

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

    def test_known_ocr_unit_confusions_are_resolved(self):
        # Readings observed on the supplied KISIM screenshot and PDF.
        for raw,lab_id,unit in [("GN","thrombozyten","G/l"),("GA","leukozyten","G/l"),("Gi","leukozyten","G/l"),
                                ("GI","thrombozyten","G/l"),("pmol/l","kreatinin","µmol/l"),("pmol","kreatinin","µmol/l"),
                                ("ymol/l","kreatinin","µmol/l"),("mmol","kalium","mmol/l"),("mmol/!","natrium","mmol/l"),
                                ("mi/min/1.7m?","egfr","ml/min/1.7m²"),("ml/min/1.7m*","egfr","ml/min/1.7m²"),
                                ("IN","haematokrit","l/l"),("il","haematokrit","l/l")]:
            self.assertEqual(normalize_import_unit(raw,lab_id,ocr=True),unit,raw)

    def test_ocr_unit_confusions_never_guess_between_allowed_units(self):
        # Hb allows g/l and g/dl: a lost tail must not be completed to g/l.
        for raw in ["g","gN","gi","g/"]:
            self.assertEqual(normalize_import_unit(raw,"hb",ocr=True),"",raw)
        # pmol/l is a real unit for Vitamin B12 and must not become µmol/l.
        self.assertEqual(normalize_import_unit("pmol/l","vitamin_b12",ocr=True),"pmol/l")
        # Corrections only apply to OCR readings, never to PDF text.
        self.assertEqual(normalize_import_unit("GN","thrombozyten"),"")
        self.assertEqual(normalize_import_unit("mol/l","kreatinin",ocr=True),"")
        self.assertEqual(normalize_import_unit("WV","haematokrit",ocr=True),"")

    def test_ocr_requires_review(self):
        v=self.parse([("CRP","18","mg/l","<5")],method="ocr")["suggestions"][0]
        self.assertEqual(v["status"],"review")

    def test_old_or_missing_headers_rejected(self):
        words=report([("CRP","18","mg/l","<5")])
        words=[w for w in words if w.text!="Resultat"]
        result=parse_positioned_words(words,page=1,width=1000,method="pdf_text")
        self.assertFalse(result["layoutRecognized"])
        self.assertEqual(result["suggestions"],[])

    def test_sample_time_is_not_read(self):
        result=self.parse([("CRP","18","mg/l","<5")])
        self.assertNotIn("measurementTimes",result)
        self.assertNotIn("measurementAt",result["suggestions"][0])
        self.assertEqual(result["suggestions"][0]["status"],"ready")


class RedValueTests(unittest.TestCase):
    """Red (abnormal) results are re-read from the color image and need agreement."""

    def run_refine(self, readings, color="red"):
        import time
        from unittest.mock import patch
        from PIL import Image, ImageDraw
        from . import service
        image = Image.new("RGB", (1000, 300), "white")
        ImageDraw.Draw(image).rectangle((582, 141, 608, 149), fill=(222, 40, 48) if color == "red" else (0, 0, 0))
        words = report([("HbA1c", "89", "%", "<5.7")])
        calls = iter(readings)
        with patch.object(service, "_read_value_cell", side_effect=lambda cell, deadline: next(calls)) as read:
            refined = service._refine_red_values(image, words, time.monotonic() + 30)
        result = parse_positioned_words(refined, page=1, width=1000, method="ocr")["suggestions"][0]
        return result["normalizedValue"], read.call_count

    def test_agreeing_readings_replace_the_grayscale_value(self):
        self.assertEqual(self.run_refine([("8.9", 90.0), ("8.9", 80.0)]), ("8.9", 2))

    def test_single_reading_is_used_when_the_other_is_empty(self):
        self.assertEqual(self.run_refine([("8.9", 90.0), None]), ("8.9", 2))

    def test_disagreeing_or_missing_readings_clear_the_value(self):
        self.assertEqual(self.run_refine([("8.9", 90.0), ("89", 80.0)]), ("", 2))
        self.assertEqual(self.run_refine([None, None]), ("", 2))

    def test_black_values_are_not_re_read(self):
        self.assertEqual(self.run_refine([], color="black"), ("89", 0))

    def test_footnote_reference_is_not_part_of_the_value(self):
        self.assertEqual(normalize_numeric("92 (1)"), ("", "92"))
        self.assertEqual(normalize_numeric("92(1)"), ("", "92"))
        self.assertEqual(normalize_numeric("(1)"), (None, None))
