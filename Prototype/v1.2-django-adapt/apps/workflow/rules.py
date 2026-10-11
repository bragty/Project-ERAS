def can_archive(summary):
    """A case is archivable only when the server-computed checklist is complete."""
    return bool(summary.get("complete"))
