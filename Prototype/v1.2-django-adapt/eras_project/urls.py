from django.conf import settings
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "ERAS Backoffice"
admin.site.site_title = "ERAS Admin"
admin.site.index_title = "Verwaltung"

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/", include("api.urls")),
    path("", include("eras.urls")),
]
