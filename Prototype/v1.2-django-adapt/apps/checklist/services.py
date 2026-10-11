from .schema import ALL_ITEM_IDS, CURRENT_SCHEMA_VERSION, PATH_ITEM_IDS, PREOP_ITEM_IDS


def current_schema_metadata():
    """Application-facing metadata for the checklist version used by this prototype."""
    return {
        "schemaVersion": CURRENT_SCHEMA_VERSION,
        "counts": {
            "preop": len(PREOP_ITEM_IDS),
            "path": len(PATH_ITEM_IDS),
            "total": len(ALL_ITEM_IDS),
        },
    }
