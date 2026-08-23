"""Wiring the four pieces together into one planned trip.

    places   what the driver typed  ->  coordinates
    routing  coordinates            ->  geometry, per-leg distance and time
    hos      an itinerary           ->  duty segments obeying 49 CFR 395.3
    logsheet duty segments          ->  one drawable sheet per day

Only the routing step leaves the process, and it goes out once. Everything
after it is arithmetic over the response that came back.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone as django_timezone

from apps.planner import places
from apps.planner.errors import PlannerError
from apps.planner.hos import (
    DutyStatus,
    Plan,
    Rules,
    StopKind,
    build_itinerary,
    plan_trip,
)
from apps.planner.logsheet import LogSheet, build_log_sheets
from apps.planner.models import Trip
from apps.planner.routing import Coordinate, RouteResult, driving_hours, fetch_route

logger = logging.getLogger(__name__)

# How a stop reads in the interface, and what colour it earns on the map.
STOP_WORDING = {
    StopKind.START: "Trip start",
    StopKind.PICKUP: "Pickup",
    StopKind.DROPOFF: "Dropoff",
    StopKind.FUEL: "Fuel stop",
    StopKind.BREAK: "30-minute break",
    StopKind.REST: "10-hour rest",
    StopKind.RESTART: "34-hour restart",
}


class UnknownTimeZone(PlannerError):
    code = "unknown_time_zone"


def _iso(moment: datetime, zone: ZoneInfo) -> str:
    """A timestamp in home-terminal time, to the second.

    The engine works in floating-point hours, so a stretch of 6.28 hours lands
    on a fraction of a second. Nobody dispatches to a tenth of a second and
    "11:16:38.100000" reads like a bug, so the sub-second part is dropped on
    the way out. The plan itself keeps full precision.
    """
    local = moment.astimezone(zone)
    if local.microsecond >= 500_000:
        local += timedelta(seconds=1)
    return local.replace(microsecond=0).isoformat()


def resolve_zone(name: str | None) -> ZoneInfo:
    """The home terminal's time zone, which is what a log sheet is kept in."""
    try:
        return ZoneInfo(name or settings.TIME_ZONE)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise UnknownTimeZone(
            f"{name!r} is not a time zone this server recognises. "
            "Use a name like 'America/Chicago'."
        ) from exc


def fingerprint(payload: dict) -> str:
    """A stable key for a set of trip inputs.

    Planning is a pure function of these values, so an identical request can
    be answered from the last one rather than routed again.
    """
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:32]


def plan_and_store(payload: dict) -> dict:
    """Plan a trip, saving it so the result has a URL of its own.

    An identical set of inputs returns the trip already computed for them,
    which keeps a reload or a double-click off the routing service.
    """
    key = f"trip:{fingerprint(payload)}"
    existing_id = cache.get(key)
    if existing_id:
        trip = Trip.objects.filter(pk=existing_id).first()
        if trip is not None:
            logger.info("Serving trip %s from cache", trip.pk)
            return trip.plan

    began = time.perf_counter()
    result = compute(payload)
    result["meta"]["computed_ms"] = round((time.perf_counter() - began) * 1000, 1)

    trip = Trip.objects.create(
        current_location=payload["current_location"],
        pickup_location=payload["pickup_location"],
        dropoff_location=payload["dropoff_location"],
        current_cycle_used_hours=payload["current_cycle_used_hours"],
        start_datetime=result["inputs"]["start_datetime"],
        driver_name=payload.get("driver_name", ""),
        carrier_name=payload.get("carrier_name", ""),
        truck_number=payload.get("truck_number", ""),
        plan={},
    )
    result["id"] = str(trip.pk)
    result["created_at"] = trip.created_at.isoformat()
    trip.plan = result
    trip.save(update_fields=["plan"])

    cache.set(key, str(trip.pk), settings.CACHES["default"].get("TIMEOUT", 3600))
    return result


def compute(payload: dict) -> dict:
    """Everything from four typed fields to a set of log sheets."""
    rules = Rules.from_settings()
    zone = resolve_zone(payload.get("timezone"))
    index = places.get_index()

    start = payload.get("start_datetime") or django_timezone.now().astimezone(zone)
    if isinstance(start, datetime) and django_timezone.is_naive(start):
        start = start.replace(tzinfo=zone)
    # Whole minutes: nobody dispatches on a half-second, and it makes an
    # identical request identical.
    start = start.replace(second=0, microsecond=0)

    current = places.resolve(payload["current_location"], index=index)
    pickup = places.resolve(payload["pickup_location"], index=index)
    dropoff = places.resolve(payload["dropoff_location"], index=index)

    route = fetch_route([
        Coordinate(current.latitude, current.longitude),
        Coordinate(pickup.latitude, pickup.longitude),
        Coordinate(dropoff.latitude, dropoff.longitude),
    ])
    to_pickup, to_dropoff = route.legs

    def locate(mile: float) -> str:
        latitude, longitude = route.coordinate_at(mile)
        found = index.nearest(latitude, longitude)
        return found.label if found else f"Mile {mile:.0f}"

    plan = plan_trip(
        build_itinerary(
            miles_to_pickup=to_pickup.distance_miles,
            hours_to_pickup=driving_hours(route, to_pickup.duration_hours),
            pickup_label=pickup.label,
            miles_to_dropoff=to_dropoff.distance_miles,
            hours_to_dropoff=driving_hours(route, to_dropoff.duration_hours),
            dropoff_label=dropoff.label,
            rules=rules,
        ),
        start=start,
        cycle_used_hours=payload["current_cycle_used_hours"],
        rules=rules,
        locate=locate,
        origin_label=current.label,
    )

    sheets = build_log_sheets(
        plan, zone=zone, origin_label=current.label, rules=rules
    )

    if plan.violations:
        logger.warning("Plan finished with %d violations", len(plan.violations))

    return {
        "id": None,
        "created_at": None,
        "inputs": {
            "current_location": current.as_dict(),
            "pickup_location": pickup.as_dict(),
            "dropoff_location": dropoff.as_dict(),
            "current_cycle_used_hours": payload["current_cycle_used_hours"],
            "start_datetime": _iso(start, zone),
            "timezone": str(zone),
            "driver_name": payload.get("driver_name", ""),
            "carrier_name": payload.get("carrier_name", ""),
            "truck_number": payload.get("truck_number", ""),
        },
        "route": _route_payload(route, current, pickup, dropoff),
        "stops": _stops_payload(plan, route, current, zone),
        "segments": _segments_payload(plan, zone),
        "logs": [_sheet_payload(sheet) for sheet in sheets],
        "summary": _summary_payload(plan, sheets, rules, zone),
        "meta": {
            "provider": route.provider,
            "api_calls": route.api_calls,
            "route_fetch_ms": round(route.fetch_ms, 1),
            "geometry_points": len(route.simplified()),
            "truck_speed_factor": settings.TRUCK_SPEED_FACTOR,
        },
    }


def _route_payload(route: RouteResult, current, pickup, dropoff) -> dict:
    labels = [current.label, pickup.label, dropoff.label]
    return {
        "geometry": [[round(lat, 5), round(lon, 5)] for lat, lon in route.simplified()],
        "bbox": [round(value, 5) for value in route.bbox()],
        "distance_miles": round(route.distance_miles, 1),
        "drive_hours": round(driving_hours(route, route.duration_hours), 2),
        "legs": [
            {
                "from": labels[index],
                "to": labels[index + 1],
                "distance_miles": round(leg.distance_miles, 1),
                "drive_hours": round(driving_hours(route, leg.duration_hours), 2),
                "start_mile": round(leg.start_mile, 1),
                "end_mile": round(leg.end_mile, 1),
            }
            for index, leg in enumerate(route.legs)
        ],
    }


def _stops_payload(plan: Plan, route: RouteResult, current, zone: ZoneInfo) -> list[dict]:
    """Everywhere the truck is stationary, in the order the driver reaches them.

    The origin is included even though it is not a segment, because a map
    with no marker at the start looks broken.
    """
    latitude, longitude = route.coordinate_at(0.0)
    stops = [
        {
            "seq": 1,
            "kind": StopKind.START.value,
            "title": STOP_WORDING[StopKind.START],
            "location": current.label,
            "latitude": round(latitude, 5),
            "longitude": round(longitude, 5),
            "mile_marker": 0.0,
            "arrive": None,
            "depart": _iso(plan.start, zone),
            "duration_hours": 0.0,
        }
    ]

    for segment in plan.segments:
        if segment.status is DutyStatus.DRIVING:
            continue
        latitude, longitude = route.coordinate_at(segment.start_mile)
        stops.append(
            {
                "seq": len(stops) + 1,
                "kind": segment.kind.value,
                "title": STOP_WORDING.get(segment.kind, segment.label),
                "location": segment.location,
                "latitude": round(latitude, 5),
                "longitude": round(longitude, 5),
                "mile_marker": round(segment.start_mile, 1),
                "arrive": _iso(segment.start, zone),
                "depart": _iso(segment.end, zone),
                "duration_hours": round(segment.hours, 2),
            }
        )

    return stops


def _segments_payload(plan: Plan, zone: ZoneInfo) -> list[dict]:
    return [
        {
            "status": segment.status.value,
            "kind": segment.kind.value,
            "start": _iso(segment.start, zone),
            "end": _iso(segment.end, zone),
            "hours": round(segment.hours, 3),
            "miles": round(segment.miles, 1),
            "label": segment.label,
            "location": segment.location,
            "start_mile": round(segment.start_mile, 1),
            "end_mile": round(segment.end_mile, 1),
        }
        for segment in plan.segments
    ]


def _sheet_payload(sheet: LogSheet) -> dict:
    return {
        "date": sheet.date.isoformat(),
        "sheet_number": sheet.sheet_number,
        "of": sheet.of,
        "from_label": sheet.from_label,
        "to_label": sheet.to_label,
        "total_miles_driving": sheet.total_miles_driving,
        "total_mileage": sheet.total_mileage,
        "entries": [
            {
                "status": entry.status.value,
                "row": entry.status.row,
                "start_hour": round(entry.start_hour, 4),
                "end_hour": round(entry.end_hour, 4),
                "hours": round(entry.hours, 4),
            }
            for entry in sheet.entries
        ],
        "remarks": [
            {
                "hour": round(remark.hour, 4),
                "text": remark.text,
                "location": remark.location,
                "kind": remark.kind.value,
            }
            for remark in sheet.remarks
        ],
        "totals": sheet.totals,
        "recap": {
            "on_duty_today": sheet.recap.on_duty_today,
            "on_duty_last_8": sheet.recap.on_duty_last_8,
            "available_tomorrow": sheet.recap.available_tomorrow,
            "on_duty_last_7": sheet.recap.on_duty_last_7,
        },
    }


def _summary_payload(
    plan: Plan, sheets: list[LogSheet], rules: Rules, zone: ZoneInfo
) -> dict:
    return {
        "days": len(sheets),
        "total_miles": round(plan.total_miles, 1),
        "drive_hours": round(plan.driving_hours, 2),
        "on_duty_hours": round(plan.on_duty_hours, 2),
        "off_duty_hours": round(plan.hours_in(DutyStatus.OFF_DUTY), 2),
        "sleeper_hours": round(plan.hours_in(DutyStatus.SLEEPER), 2),
        "elapsed_hours": round(plan.elapsed_hours, 2),
        "departure": _iso(plan.start, zone),
        "arrival": _iso(plan.finish, zone),
        "average_speed_mph": (
            round(plan.total_miles / plan.driving_hours, 1)
            if plan.driving_hours > 0
            else 0.0
        ),
        "fuel_stops": plan.count(StopKind.FUEL),
        "rest_breaks": plan.count(StopKind.BREAK),
        "rests": plan.count(StopKind.REST),
        "restarts": plan.count(StopKind.RESTART),
        "cycle_hours_at_start": round(plan.cycle_hours_at_start, 2),
        "cycle_hours_at_finish": round(plan.cycle_hours_at_finish, 2),
        "cycle_hours_available": round(
            max(rules.cycle_limit_hours - plan.cycle_hours_at_finish, 0.0), 2
        ),
        "compliant": not plan.violations,
        "violations": plan.violations,
    }
