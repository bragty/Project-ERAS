from django.views.decorators.http import require_GET

from apps.core.api import ok

from ..schema import ALL_ITEM_IDS, CURRENT_SCHEMA_VERSION, FIELD_RULES, PATH_ITEM_IDS, PREOP_ITEM_IDS


@require_GET
def schema_info(request):
    return ok(
        {
            "schemaVersion": CURRENT_SCHEMA_VERSION,
            "counts": {
                "preop": len(PREOP_ITEM_IDS),
                "path": len(PATH_ITEM_IDS),
                "total": len(ALL_ITEM_IDS),
            },
            "fieldRules": FIELD_RULES,
        }
    )
