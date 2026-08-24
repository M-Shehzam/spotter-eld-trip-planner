"""Fetching a route, and turning it into something the planner can measure.

The whole trip is one request: current location, then pickup, then dropoff.
The provider answers with the full geometry and a per-leg breakdown, and
everything downstream is computed locally from that: where the fuel stop
lands, where the driver parks for ten hours, what town goes in the remarks,
all from
single response.

That matters because the planner needs a coordinate for roughly a dozen stops
per trip. Asking the router for each one would turn one call into thirteen.
Instead, ``RouteResult`` carries a cumulative-mileage profile, and any mile
marker interpolates to a point on the line.

Providers and the polyline codec are carried over from
spotter-fuel-route-api; the waypoint support and the distance profile are new.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Protocol

import httpx
import numpy as np
from django.conf import settings

from apps.planner.errors import PlannerError
from apps.planner.geo import cumulative_miles
from apps.planner.polyline import decode

logger = logging.getLogger(__name__)

METRES_PER_MILE = 1609.344


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------


class RoutingError(PlannerError):
    code = "routing_error"


class RouteNotFound(RoutingError):
    """The provider answered, but no drivable route connects the points."""

    code = "route_not_found"


class RoutingUnavailable(RoutingError):
    """The provider could not be reached, timed out, or returned a 5xx."""

    code = "routing_unavailable"
    http_status = 503


class RoutingRequestInvalid(RoutingError):
    """The provider rejected the request, usually bad coordinates."""

    code = "routing_request_invalid"


# --------------------------------------------------------------------------
# Values
# --------------------------------------------------------------------------


@dataclass(slots=True)
class Coordinate:
    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not -90.0 <= self.latitude <= 90.0:
            raise ValueError(f"Latitude out of range: {self.latitude}")
        if not -180.0 <= self.longitude <= 180.0:
            raise ValueError(f"Longitude out of range: {self.longitude}")


@dataclass(slots=True)
class RouteLeg:
    """One waypoint-to-waypoint stretch, positioned on the overall route."""

    distance_miles: float
    duration_hours: float
    start_mile: float
    end_mile: float


@dataclass(slots=True)
class RouteResult:
    """A driving route, already in the units the rest of the app uses."""

    coordinates: list[tuple[float, float]]
    distance_miles: float
    duration_hours: float
    legs: list[RouteLeg]
    provider: str
    api_calls: int = 1
    fetch_ms: float = 0.0
    _profile: np.ndarray | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self._profile = self._build_profile()

    def _build_profile(self) -> np.ndarray:
        """Cumulative miles at each vertex, reconciled with the reported total.

        Summing haversine hops along the decoded line lands within a fraction
        of a percent of the distance the provider reports, the gap being
        polyline rounding. Scaling the profile onto the reported total keeps
        one number authoritative, so a stop at "mile 1000" means the same
        thing in the summary, on the map and on the log sheet.
        """
        latitudes = np.fromiter((lat for lat, _ in self.coordinates), dtype=np.float64)
        longitudes = np.fromiter((lon for _, lon in self.coordinates), dtype=np.float64)
        profile = cumulative_miles(latitudes, longitudes)

        measured = float(profile[-1]) if profile.size else 0.0
        if measured > 0 and self.distance_miles > 0:
            profile *= self.distance_miles / measured
        return profile

    @property
    def profile(self) -> np.ndarray:
        assert self._profile is not None
        return self._profile

    @property
    def point_count(self) -> int:
        return len(self.coordinates)

    def coordinate_at(self, mile: float) -> tuple[float, float]:
        """The point on the route at a given distance from the start.

        Interpolates between the two vertices the mile marker falls between,
        so a fuel stop at mile 1000 sits on the line rather than at the
        nearest shape point.
        """
        if not self.coordinates:
            raise RoutingUnavailable("The route has no geometry to measure.")

        profile = self.profile
        clamped = min(max(mile, 0.0), float(profile[-1]))
        position = int(np.searchsorted(profile, clamped, side="right"))

        if position <= 0:
            return self.coordinates[0]
        if position >= len(self.coordinates):
            return self.coordinates[-1]

        before_mile = float(profile[position - 1])
        after_mile = float(profile[position])
        span = after_mile - before_mile
        fraction = 0.0 if span <= 0 else (clamped - before_mile) / span

        lat1, lon1 = self.coordinates[position - 1]
        lat2, lon2 = self.coordinates[position]
        return (lat1 + (lat2 - lat1) * fraction, lon1 + (lon2 - lon1) * fraction)

    def as_geojson(self) -> dict:
        """GeoJSON wants (longitude, latitude); we carry (latitude, longitude)."""
        return {
            "type": "LineString",
            "coordinates": [[round(lon, 6), round(lat, 6)] for lat, lon in self.coordinates],
        }

    def bbox(self) -> list[float]:
        """``[west, south, east, north]`` for fitting a map viewport."""
        lats = [lat for lat, _ in self.coordinates]
        lons = [lon for _, lon in self.coordinates]
        return [min(lons), min(lats), max(lons), max(lats)]

    def simplified(self, max_points: int = 1500) -> list[tuple[float, float]]:
        """Evenly thinned geometry, for shipping to the map.

        A transcontinental route decodes to tens of thousands of vertices,
        which is far more than a Leaflet polyline needs and a large share of
        the response body. Distances are always measured on the full profile;
        only what crosses the wire is thinned.
        """
        if len(self.coordinates) <= max_points:
            return self.coordinates

        step = len(self.coordinates) / max_points
        picked = [self.coordinates[int(index * step)] for index in range(max_points)]
        picked[-1] = self.coordinates[-1]
        return picked


# --------------------------------------------------------------------------
# Provider protocol and shared client
# --------------------------------------------------------------------------


class RoutingProvider(Protocol):
    name: str

    def route(self, waypoints: list[Coordinate]) -> RouteResult: ...


_client: httpx.Client | None = None


def _shared_client() -> httpx.Client:
    """One pooled client per process, so repeat requests skip the TLS handshake."""
    global _client
    if _client is None:
        _client = httpx.Client(
            timeout=httpx.Timeout(settings.ROUTING_TIMEOUT_SECONDS, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            headers={"User-Agent": "spotter-eld-trip-planner/1.0"},
            follow_redirects=True,
        )
    return _client


def reset_client() -> None:
    """Drop the pooled client. Used by tests."""
    global _client
    if _client is not None:
        _client.close()
    _client = None


def _legs_from_distances(
    distances: list[float], durations: list[float]
) -> list[RouteLeg]:
    legs: list[RouteLeg] = []
    travelled = 0.0
    for distance, duration in zip(distances, durations, strict=True):
        legs.append(
            RouteLeg(
                distance_miles=distance,
                duration_hours=duration,
                start_mile=travelled,
                end_mile=travelled + distance,
            )
        )
        travelled += distance
    return legs


# --------------------------------------------------------------------------
# OSRM
# --------------------------------------------------------------------------


@dataclass(slots=True)
class OSRMProvider:
    """Open Source Routing Machine. No API key required.

    ``overview=full`` keeps enough shape points that interpolating a mile
    marker lands on the road, and ``polyline6`` keeps the payload small.
    """

    name: str = "osrm"
    base_url: str = field(default_factory=lambda: settings.OSRM_BASE_URL)

    def route(self, waypoints: list[Coordinate]) -> RouteResult:
        if len(waypoints) < 2:
            raise RoutingRequestInvalid("A route needs at least two waypoints.")

        path = ";".join(f"{point.longitude},{point.latitude}" for point in waypoints)
        url = f"{self.base_url.rstrip('/')}/route/v1/driving/{path}"
        params = {
            "overview": "full",
            "geometries": "polyline6",
            "steps": "false",
            "alternatives": "false",
            "annotations": "false",
        }

        began = time.perf_counter()
        try:
            response = _shared_client().get(url, params=params)
        except httpx.TimeoutException as exc:
            raise RoutingUnavailable(
                f"The routing service timed out after "
                f"{settings.ROUTING_TIMEOUT_SECONDS:.0f} seconds. Please try again."
            ) from exc
        except httpx.HTTPError as exc:
            raise RoutingUnavailable(
                "The routing service could not be reached. Please try again."
            ) from exc
        elapsed_ms = (time.perf_counter() - began) * 1000

        if response.status_code >= 500:
            raise RoutingUnavailable(f"The routing service returned {response.status_code}.")
        if response.status_code == 429:
            raise RoutingUnavailable("The routing service is rate limiting this client.")

        try:
            payload = response.json()
        except ValueError as exc:
            raise RoutingUnavailable("The routing service returned an unreadable body.") from exc

        code = payload.get("code", "")
        if code in {"NoRoute", "NoSegment", "NoTrips"}:
            raise RouteNotFound(
                "No drivable route connects those locations. Each one has to be "
                "reachable by road within the United States."
            )
        if code != "Ok":
            message = payload.get("message", code or "unknown error")
            if response.status_code == 400:
                raise RoutingRequestInvalid(f"The routing service rejected the request: {message}")
            raise RoutingUnavailable(f"Routing failed: {message}")

        routes = payload.get("routes") or []
        if not routes:
            raise RouteNotFound("The routing service returned no route.")

        best = routes[0]
        coordinates = decode(best.get("geometry", ""), precision=6)
        if len(coordinates) < 2:
            raise RoutingUnavailable("The routing service returned an unusable geometry.")

        raw_legs = best.get("legs") or []
        distances = [float(leg["distance"]) / METRES_PER_MILE for leg in raw_legs]
        durations = [float(leg["duration"]) / 3600.0 for leg in raw_legs]

        return RouteResult(
            coordinates=coordinates,
            distance_miles=float(best["distance"]) / METRES_PER_MILE,
            duration_hours=float(best["duration"]) / 3600.0,
            legs=_legs_from_distances(distances, durations),
            provider=self.name,
            api_calls=1,
            fetch_ms=elapsed_ms,
        )


# --------------------------------------------------------------------------
# Valhalla
# --------------------------------------------------------------------------


@dataclass(slots=True)
class ValhallaProvider:
    """FOSSGIS Valhalla. No API key, and it costs the route as a truck.

    Kept as the standby for when the OSRM demo server is unavailable. Because
    it applies truck costing, its durations need no speed factor; the planner
    checks the provider name before applying one.
    """

    name: str = "valhalla"
    base_url: str = field(default_factory=lambda: settings.OSRM_FALLBACK_URL)

    def route(self, waypoints: list[Coordinate]) -> RouteResult:
        if len(waypoints) < 2:
            raise RoutingRequestInvalid("A route needs at least two waypoints.")

        url = f"{self.base_url.rstrip('/')}/route"
        body = {
            "locations": [
                {"lat": point.latitude, "lon": point.longitude} for point in waypoints
            ],
            "costing": "truck",
            "units": "miles",
            "directions_options": {"units": "miles"},
        }

        began = time.perf_counter()
        try:
            response = _shared_client().post(url, json=body)
        except httpx.TimeoutException as exc:
            raise RoutingUnavailable("The standby routing service timed out.") from exc
        except httpx.HTTPError as exc:
            raise RoutingUnavailable("The standby routing service could not be reached.") from exc
        elapsed_ms = (time.perf_counter() - began) * 1000

        if response.status_code >= 500:
            raise RoutingUnavailable(f"The standby routing service returned {response.status_code}.")

        try:
            payload = response.json()
        except ValueError as exc:
            raise RoutingUnavailable("The standby routing service returned an unreadable body.") from exc

        if response.status_code == 400 or "error" in payload:
            message = payload.get("error", "unknown error")
            # 442 and 443 are Valhalla's "no route between locations".
            if payload.get("error_code") in {442, 443}:
                raise RouteNotFound(
                    "No drivable route connects those locations. Each one has to be "
                    "reachable by road within the United States."
                )
            raise RoutingRequestInvalid(f"The standby routing service rejected the request: {message}")

        trip = payload.get("trip") or {}
        raw_legs = trip.get("legs") or []
        if not raw_legs:
            raise RouteNotFound("The standby routing service returned no route.")

        coordinates: list[tuple[float, float]] = []
        distances: list[float] = []
        durations: list[float] = []
        for leg in raw_legs:
            coordinates.extend(decode(leg.get("shape", ""), precision=6))
            summary = leg.get("summary") or {}
            distances.append(float(summary.get("length", 0.0)))
            durations.append(float(summary.get("time", 0.0)) / 3600.0)

        if len(coordinates) < 2:
            raise RoutingUnavailable("The standby routing service returned an unusable geometry.")

        summary = trip.get("summary") or {}
        return RouteResult(
            coordinates=coordinates,
            distance_miles=float(summary.get("length", sum(distances))),
            duration_hours=float(summary.get("time", 0.0)) / 3600.0,
            legs=_legs_from_distances(distances, durations),
            provider=self.name,
            api_calls=1,
            fetch_ms=elapsed_ms,
        )


# --------------------------------------------------------------------------
# Selection
# --------------------------------------------------------------------------


def fetch_route(waypoints: list[Coordinate]) -> RouteResult:
    """Fetch the whole trip in one call, falling back only on failure.

    A healthy request makes one external call. The standby fires when the
    primary is unreachable or broken, never to improve a result, so the second
    call is recovery rather than routine.
    """
    primary = OSRMProvider()
    try:
        return primary.route(waypoints)
    except (RouteNotFound, RoutingRequestInvalid):
        # A definitive answer. Asking a second provider would not change it.
        raise
    except RoutingUnavailable as exc:
        if not settings.OSRM_FALLBACK_URL:
            raise

        logger.warning("OSRM unavailable (%s); trying the standby provider", exc)
        result = ValhallaProvider().route(waypoints)
        # Report both attempts, so the response never understates its egress.
        result.api_calls = 2
        return result


def driving_hours(result: RouteResult, duration_hours: float) -> float:
    """Convert a provider duration into planned truck driving time.

    OSRM's demo profile costs the route as a car, but it respects posted
    limits and comes out conservative: measured across five long hauls it
    implies 48-58 mph, which is already the band a dispatcher plans a Class 8
    truck at. TRUCK_SPEED_FACTOR therefore defaults to 1.0 and exists as a
    tuning knob rather than a correction. Valhalla costs as a truck, so its
    durations are used as they are regardless of the factor.
    """
    if result.provider == "valhalla":
        return duration_hours
    return duration_hours * settings.TRUCK_SPEED_FACTOR
