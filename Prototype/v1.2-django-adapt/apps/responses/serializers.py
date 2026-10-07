def checklist_state_to_dict(state_obj, state, summary, derived, errors):
    return {
        "state": state,
        "summary": summary,
        "derived": derived,
        "validationErrors": errors,
        "revision": state_obj.revision,
        "savedAt": state_obj.updated_at.isoformat() if state_obj.updated_at else None,
    }
