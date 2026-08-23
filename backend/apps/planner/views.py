"""HTTP surface for the planner."""

from __future__ import annotations

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.planner import places, services
from apps.planner.models import Trip
from apps.planner.serializers import TripRequestSerializer


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
                "plan_a_trip": "POST /api/v1/trips/",
                "retrieve_a_trip": "/api/v1/trips/{id}/",
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


@api_view(["POST"])
def plan_trip(request):
    """Plan a trip and keep it, so the result has a URL that can be shared."""
    form = TripRequestSerializer(data=request.data)
    form.is_valid(raise_exception=True)
    return Response(
        services.plan_and_store(form.validated_data),
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
def retrieve_trip(request, trip_id):
    """A trip already planned. Reloading a shared link costs no routing call."""
    trip = get_object_or_404(Trip, pk=trip_id)
    return Response(trip.plan)
