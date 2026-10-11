from django.urls import path

from .views import lab_import, schema_info

app_name = "checklist_api"

urlpatterns = [
    path("checklist/schema/", schema_info, name="schema"),
    path("cases/<str:case_number>/labs/import/", lab_import, name="lab-import"),
]
