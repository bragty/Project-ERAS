from django.urls import path

from .views import case_detail, patients_collection

app_name = "patients_api"

urlpatterns = [
    path("patients/", patients_collection, name="patients"),
    path("cases/<str:case_number>/", case_detail, name="case-detail"),
]
