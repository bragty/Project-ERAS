from django.urls import path

from .views import case_state

app_name = "responses_api"

urlpatterns = [
    path("cases/<str:case_number>/state/", case_state, name="case-state"),
]
