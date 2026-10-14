from django.urls import path

from .views import case_state, case_state_revision

app_name = "responses_api"

urlpatterns = [
    path("cases/<str:case_number>/state/", case_state, name="case-state"),
    path("cases/<str:case_number>/state/revision/", case_state_revision, name="case-state-revision"),
]
