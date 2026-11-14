from apps.responses.models import ChecklistState


def archived_cases_csv(cases):
    """Structured export in long form, one row per saved leaf value.

    Fields stay addressable even when a questionnaire or dynamic list grows.
    Empty containers and nulls have explicit types, rather than disappearing.
    """
    import csv
    import json
    from datetime import date, datetime
    from django.http import StreamingHttpResponse
    from django.utils import timezone
    from apps.audit.services import record_event
    from apps.checklist.definition import base_definition, iter_items

    definition = base_definition()
    labels = {key: spec["label"] for key, spec in definition["fields"].items()}
    labels.update({item["id"]: item["title"] for _section, item in iter_items(definition)})

    def leaves(value, path="", label=""):
        if isinstance(value, dict) and value:
            for key, child in value.items():
                # JSON Pointer escaping keeps keys containing / or ~ unambiguous.
                part = str(key).replace("~", "~0").replace("/", "~1")
                yield from leaves(child, path + "/" + part, labels.get(str(key), str(key)))
        elif isinstance(value, list) and value:
            for index, child in enumerate(value):
                yield from leaves(child, path + "/" + str(index), label)
        else:
            kind = ("null" if value is None else "boolean" if isinstance(value, bool) else
                    "number" if isinstance(value, (int, float)) else "object" if isinstance(value, dict) else
                    "array" if isinstance(value, list) else "datetime" if isinstance(value, datetime) else
                    "date" if isinstance(value, date) else "string")
            text = json.dumps(value, ensure_ascii=False) if kind in {"null", "boolean", "number", "object", "array"} else str(value)
            yield path, label, kind, text

    def model_data(obj, *, exclude=()):
        return {field.name: getattr(obj, field.attname) for field in obj._meta.concrete_fields if field.name not in exclude}

    def safe_cell(value):
        text = str(value)
        # Protect spreadsheet applications from interpreting user-entered text
        # as a formula. This includes formulas hidden behind leading whitespace.
        if text.startswith(("\t", "\r", "\n")) or text.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + text
        return text

    class Echo:
        def write(self, text):
            return text

    writer = csv.writer(Echo(), delimiter=";", lineterminator="\r\n")
    count = cases.count()
    record_event(event_type="archived_patients_exported", entity_type="TreatmentCase", metadata={"caseCount": count})

    def rows():
        yield "\ufeff"
        yield writer.writerow(["Patient-UUID", "Patienten-ID", "Geschlecht", "Fall-UUID", "Fallnummer (technisch)",
                               "OP-Datum", "Datengruppe", "Feldpfad", "Bezeichnung", "Datentyp", "Wert"])
        # Read persisted snapshots, never migrate/recompute or save answers while exporting.
        for case in cases.prefetch_related("audit_events").iterator(chunk_size=100):
            identity = [case.patient_id, case.patient.patient_number or "",
                        case.patient.get_sex_display() or "", case.pk, case.case_number,
                        case.op_date.isoformat() if case.op_date else ""]
            groups = [("Patient", model_data(case.patient)), ("Behandlungsfall", model_data(case))]
            try:
                state = case.checklist_state
            except ChecklistState.DoesNotExist:
                groups.append(("Checkliste", None))
            else:
                groups.extend([("Checklisten-Metadaten", model_data(state, exclude=("state",))), ("Checkliste", state.state)])
            groups.append(("Audit", [model_data(event) for event in case.audit_events.all()]))
            for group, data in groups:
                for path, label, kind, value in leaves(data):
                    yield writer.writerow([safe_cell(cell) for cell in [*identity, group, path, label, kind, value]])

    response = StreamingHttpResponse(rows(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="BENE-Archiv-{timezone.localdate().isoformat()}.csv"'
    response["Cache-Control"] = "no-store"
    return response


def case_to_dict(case, *, include_deletion=False):
    try:
        state = case.checklist_state
    except ChecklistState.DoesNotExist:
        state = None
    result = {
        "id": str(case.id),
        "patientId": str(case.patient_id),
        "patientNumber": case.patient.patient_number or "",
        "sex": case.patient.sex,
        # Technical key for API calls only; the frontend does not display it.
        "caseNumber": case.case_number,
        "opDate": case.op_date.isoformat() if case.op_date else "",
        "procedure": case.procedure_type.name if case.procedure_type else case.procedure,
        "procedureTypeId": case.procedure_type_id,
        "surgeon": case.surgeon,
        "beneNurse": case.bene_nurse,
        "beneDeputy": case.bene_deputy,
        "archived": case.archived,
        "progress": state.progress_total if state else 0,
        "progressPreop": state.progress_preop if state else 0,
        "progressPath": state.progress_path if state else 0,
        "complete": bool(state.complete) if state else False,
        "updatedAt": case.updated_at.isoformat(),
    }
    if include_deletion:
        from .services import patient_deletion_token
        result["deletionToken"], result["patientCaseCount"] = patient_deletion_token(case.patient)
    return result
