from django.urls import path

from .views import schema_info

app_name = "checklist_api"

urlpatterns = [
    path("checklist/schema/", schema_info, name="schema"),
]
