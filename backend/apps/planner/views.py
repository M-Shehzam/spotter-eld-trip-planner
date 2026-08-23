"""HTTP surface for the planner."""

from __future__ import annotations

from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.planner import places


@api_view(["GET"])
def service_root(request):
    """A short description, so the deployed backend is not a bare 404."""
    return Response(
        {
            "service": "Spotter ELD trip planner",
            "docs": "https://github.com/M-Shehzam/spotter-eld-trip-planner",
            "endpoints": {
                "health": "/api/v1/health/",
                "place_suggestions": "/api/v1/places/suggest/?q=",
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
            "places_indexed": len(places.get_index()),
        }
    )


@api_view(["GET"])
def suggest_places(request):
    """Autocomplete for the three location fields.

    Answers from the in-process gazetteer, so it is fast enough to call on
    every keystroke and cannot be rate-limited.
    """
    query = request.query_params.get("q", "")
    try:
        limit = min(int(request.query_params.get("limit", 8)), 20)
    except (TypeError, ValueError):
        limit = 8

    matches = places.get_index().suggest(query, limit=limit)
    return Response(
        {
            "query": query,
            "results": [
                {
                    "label": place.label,
                    "name": place.name,
                    "state": place.state,
                    "latitude": round(place.latitude, 6),
                    "longitude": round(place.longitude, 6),
                    "population": place.population,
                }
                for place in matches
            ],
        }
    )
