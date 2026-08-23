"""HTTP surface for the planner."""

from __future__ import annotations

from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def service_root(request):
    """A short description, so the deployed backend is not a bare 404."""
    return Response(
        {
            "service": "Spotter ELD trip planner",
            "docs": "https://github.com/M-Shehzam/spotter-eld-trip-planner",
            "endpoints": {
                "health": "/api/v1/health/",
            },
        }
    )


@api_view(["GET"])
def health(request):
    """Liveness probe, also used by the keep-warm ping."""
    return Response(
        {
            "status": "ok",
            "debug": settings.DEBUG,
            "routing_provider": settings.OSRM_BASE_URL,
        }
    )
