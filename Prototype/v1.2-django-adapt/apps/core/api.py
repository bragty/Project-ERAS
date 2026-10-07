import json

from django.http import JsonResponse


class ApiError(Exception):
    def __init__(self, message, *, status=400, code="bad_request", fields=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.fields = fields or {}


def parse_json_body(request):
    if not request.body:
        return {}
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApiError("Ungültiger JSON-Request.", code="invalid_json") from exc
    if not isinstance(data, dict):
        raise ApiError("Der Request-Body muss ein JSON-Objekt sein.", code="invalid_json")
    return data


def ok(data=None, *, status=200):
    return JsonResponse(data or {}, status=status, json_dumps_params={"ensure_ascii": False})


def error_response(exc):
    if isinstance(exc, ApiError):
        return ok(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "fields": exc.fields,
                }
            },
            status=exc.status,
        )
    raise exc
