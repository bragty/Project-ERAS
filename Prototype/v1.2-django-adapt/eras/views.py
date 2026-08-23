from django.shortcuts import render


def home(request):
    return render(request, "eras/pages/home.html", {"page_title": 'BENE Plattform - Frontpage V1.1'})


def checklist(request):
    return render(request, "eras/pages/checklist.html", {"page_title": 'BENE Plattform'})
