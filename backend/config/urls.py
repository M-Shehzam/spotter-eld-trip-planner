"""Root URL configuration.

Everything the frontend talks to lives under ``/api/v1/``. The bare root
answers with a short service description so that opening the deployed
backend in a browser is informative rather than a 404.
"""

from django.urls import include, path

from apps.planner.views import service_root

urlpatterns = [
    path("", service_root, name="service-root"),
    path("api/v1/", include("apps.planner.urls")),
]
