from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie


@ensure_csrf_cookie
def home(request):
    return render(request, "eras/pages/home.html", {"page_title": "BENE Plattform - Frontpage V1.1"})


@ensure_csrf_cookie
def checklist(request):
    # Every persisted checklist belongs to a treatment case. A free-floating
    # checklist is intentionally not supported by the backend architecture.
    if not request.GET.get("case"):
        return redirect("eras:home")
    return render(request, "eras/pages/checklist.html", {"page_title": "BENE Plattform"})
