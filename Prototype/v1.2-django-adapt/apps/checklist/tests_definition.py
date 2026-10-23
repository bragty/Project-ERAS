from copy import deepcopy

from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.test import SimpleTestCase
from unittest.mock import patch

from .definition import base_definition
from .definition_checks import definition_errors


class DefinitionCheckTests(SimpleTestCase):
    """definition.json is edited by hand; typical mistakes must be reported."""

    def errors_after(self, change):
        definition = deepcopy(base_definition())
        change(definition)
        return definition_errors(definition)

    def item(self, definition, item_id):
        for entry in definition["preop"]:
            if entry["id"] == item_id:
                return entry
        raise KeyError(item_id)

    def test_current_definition_is_valid(self):
        self.assertEqual(definition_errors(base_definition()), [])

    def test_typical_mistakes_are_reported(self):
        cases = {
            "kommt mehrfach vor": lambda d: d["preop"].append(deepcopy(self.item(d, "t1:pbm"))),
            "ist unter 'fields' nicht definiert": lambda d: self.item(d, "t1:pbm")["fields"].append("pbm_tippfehler"),
            "unbekannte Eigenschaft 'detial'": lambda d: self.item(d, "t1:pbm").update(detial=["x"]),
            "'title' fehlt": lambda d: self.item(d, "t1:pbm").update(title=" "),
            "ID muss mit 't1:' beginnen": lambda d: self.item(d, "t1:pbm").update(id="pbm"),
            "Typ 'zahl' ist unbekannt": lambda d: d["fields"]["kardio_ef"].update(type="zahl"),
            "braucht mindestens eine Option": lambda d: d["fields"]["pbm_status"].update(options=[]),
            "Optionswerte sind nicht eindeutig": lambda d: d["fields"]["pbm_status"]["options"].append("Eingeleitet"),
            "'min' ist grösser als 'max'": lambda d: d["fields"]["kardio_ef"].update(min=101),
            "wird von keinem Punkt verwendet": lambda d: d["fields"].update(neu={"label": "Neu", "type": "text"}),
            "die Fragen ergeben höchstens 17 Punkte": lambda d: self.item(d, "t1:fb-g8")["scoring"].update(max=18),
            "Frage 'g8_fehlt' ist kein Feld": lambda d: self.item(d, "t1:fb-g8")["scoring"]["questions"].append("g8_fehlt"),
        }
        for expected, change in cases.items():
            with self.subTest(expected):
                errors = self.errors_after(change)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_broken_definition_stops_manage_py_check(self):
        broken = deepcopy(base_definition())
        broken["fields"]["kardio_ef"]["type"] = "zahl"
        with patch("apps.checklist.definition_checks.base_definition", return_value=broken):
            with self.assertRaisesMessage(SystemCheckError, "kardio_ef"):
                call_command("check")
