from django.urls import path

from .views import archive, restore

app_name = "workflow_api"

urlpatterns = [
    path("cases/<str:case_number>/archive/", archive, name="case-archive"),
    path("cases/<str:case_number>/restore/", restore, name="case-restore"),
]
