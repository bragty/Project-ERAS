from django.urls import path

from . import views

app_name = "eras"

urlpatterns = [
    path("", views.home, name="home"),
    path("checklist/", views.checklist, name="checklist"),
]
