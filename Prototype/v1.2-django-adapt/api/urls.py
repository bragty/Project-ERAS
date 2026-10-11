from django.http import JsonResponse
from django.urls import include, path


def health(request):
    return JsonResponse({"status": "ok", "service": "eras-backend"})


urlpatterns = [
    path("health/", health, name="api-health"),
    path("", include("apps.patients.api.urls")),
    path("", include("apps.responses.api.urls")),
    path("", include("apps.workflow.api.urls")),
    path("", include("apps.checklist.api.urls")),
]
