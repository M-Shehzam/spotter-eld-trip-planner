"""P5: the HTTP surface, from four typed fields to a set of log sheets.

The routing provider is stubbed throughout. These tests are about the
contract the frontend depends on, not about whether a demo server is up.
"""

import json
from datetime import datetime, timezone

import httpx
import pytest
import respx
from django.core.cache import cache

from apps.planner import routing
from apps.planner.models import Trip
from apps.planner.polyline import encode

OSRM = "https://router.project-osrm.org/route/v1/driving/"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clean_state():
    cache.clear()
    routing.reset_client()
    yield
    cache.clear()
    routing.reset_client()


def geometry(points=400):
    """Chicago to Dallas by way of St. Louis, as a plausible line."""
    corners = [(41.85, -87.65), (38.63, -90.20), (32.78, -96.81)]
    line = []
    for (lat1, lon1), (lat2, lon2) in zip(corners, corners[1:]):
        for step in range(points // 2):
            fraction = step / (points // 2)
            line.append((lat1 + (lat2 - lat1) * fraction, lon1 + (lon2 - lon1) * fraction))
    line.append(corners[-1])
    return line


def osrm_response(leg_miles=(295.0, 629.0), leg_hours=(5.5, 11.8)):
    metres = [miles * 1609.344 for miles in leg_miles]
    seconds = [hours * 3600 for hours in leg_hours]
    return httpx.Response(
        200,
        json={
            "code": "Ok",
            "routes": [
                {
                    "geometry": encode(geometry(), precision=6),
                    "distance": sum(metres),
                    "duration": sum(seconds),
                    "legs": [
                        {"distance": m, "duration": s} for m, s in zip(metres, seconds)
                    ],
                }
            ],
        },
    )


@pytest.fixture
def route_stub():
    with respx.mock:
        yield respx.get(url__startswith=OSRM).mock(return_value=osrm_response())


VALID = {
    "current_location": "Chicago, IL",
    "pickup_location": "St. Louis, MO",
    "dropoff_location": "Dallas, TX",
    "current_cycle_used_hours": 14.5,
    "start_datetime": "2026-08-24T06:00:00-05:00",
    "timezone": "America/Chicago",
    "driver_name": "M. Shehzam",
    "carrier_name": "Spotter Logistics",
    "truck_number": "1842",
}


def post(api, **overrides):
    payload = {**VALID, **overrides}
    return api.post("/api/v1/trips/", data=json.dumps(payload), content_type="application/json")


# ==========================================================================
# The happy path
# ==========================================================================


class TestPlanningATrip:
    def test_it_answers_created(self, api, route_stub):
        assert post(api).status_code == 201

    def test_it_routes_once(self, api, route_stub):
        post(api)
        assert route_stub.call_count == 1

    def test_the_response_carries_every_section_the_interface_needs(self, api, route_stub):
        body = post(api).json()
        assert set(body) >= {
            "id", "created_at", "inputs", "route", "stops", "segments",
            "logs", "summary", "meta",
        }

    def test_the_typed_locations_come_back_resolved(self, api, route_stub):
        inputs = post(api).json()["inputs"]
        assert inputs["current_location"]["label"] == "Chicago, IL"
        assert inputs["pickup_location"]["label"] == "St. Louis, MO"
        assert inputs["dropoff_location"]["label"] == "Dallas, TX"

    def test_the_route_is_drawable(self, api, route_stub):
        route = post(api).json()["route"]
        assert len(route["geometry"]) > 100
        assert all(len(point) == 2 for point in route["geometry"])
        assert len(route["bbox"]) == 4
        assert route["distance_miles"] == pytest.approx(924.0, abs=1.0)

    def test_the_two_legs_are_reported_separately(self, api, route_stub):
        legs = post(api).json()["route"]["legs"]
        assert [leg["from"] for leg in legs] == ["Chicago, IL", "St. Louis, MO"]
        assert [leg["to"] for leg in legs] == ["St. Louis, MO", "Dallas, TX"]

    def test_the_plan_is_compliant(self, api, route_stub):
        summary = post(api).json()["summary"]
        assert summary["compliant"] is True
        assert summary["violations"] == []


# ==========================================================================
# Stops
# ==========================================================================


class TestStops:
    @pytest.fixture
    def stops(self, api, route_stub):
        return post(api).json()["stops"]

    def test_the_first_stop_is_the_origin(self, stops):
        assert stops[0]["kind"] == "start"
        assert stops[0]["mile_marker"] == 0.0
        assert stops[0]["location"] == "Chicago, IL"

    def test_every_stop_can_be_put_on_a_map(self, stops):
        for stop in stops:
            assert 24 < stop["latitude"] < 50
            assert -125 < stop["longitude"] < -66

    def test_the_pickup_and_the_dropoff_are_both_there(self, stops):
        kinds = [stop["kind"] for stop in stops]
        assert "pickup" in kinds
        assert "dropoff" in kinds

    def test_stops_are_numbered_in_the_order_they_are_reached(self, stops):
        assert [stop["seq"] for stop in stops] == list(range(1, len(stops) + 1))
        markers = [stop["mile_marker"] for stop in stops]
        assert markers == sorted(markers)

    def test_a_stop_says_how_long_the_driver_is_there(self, stops):
        pickup = next(stop for stop in stops if stop["kind"] == "pickup")
        assert pickup["duration_hours"] == pytest.approx(1.0)
        assert pickup["arrive"] and pickup["depart"]

    def test_no_driving_is_reported_as_a_stop(self, stops):
        assert "drive" not in {stop["kind"] for stop in stops}


# ==========================================================================
# Log sheets
# ==========================================================================


class TestLogSheets:
    @pytest.fixture
    def logs(self, api, route_stub):
        return post(api).json()["logs"]

    def test_there_is_a_sheet_for_every_day(self, logs):
        assert len(logs) >= 2
        assert [sheet["sheet_number"] for sheet in logs] == list(range(1, len(logs) + 1))

    def test_every_sheet_accounts_for_a_full_day(self, logs):
        for sheet in logs:
            assert sum(sheet["totals"].values()) == pytest.approx(24.0, abs=1e-3)

    def test_the_grid_is_ready_to_draw(self, logs):
        for sheet in logs:
            assert sheet["entries"][0]["start_hour"] == 0.0
            assert sheet["entries"][-1]["end_hour"] == 24.0
            for entry in sheet["entries"]:
                assert entry["row"] in {1, 2, 3, 4}

    def test_each_sheet_says_where_the_day_ran_from_and_to(self, logs):
        for sheet in logs:
            assert sheet["from_label"]
            assert sheet["to_label"]

    def test_the_recap_boxes_are_filled(self, logs):
        recap = logs[0]["recap"]
        assert recap["on_duty_last_8"] >= 14.5  # the hours the driver arrived with
        assert recap["available_tomorrow"] == pytest.approx(
            70.0 - recap["on_duty_last_8"]
        )

    def test_the_remarks_name_places(self, logs):
        assert all(remark["location"] for sheet in logs for remark in sheet["remarks"])


# ==========================================================================
# Validation
# ==========================================================================


class TestValidation:
    @pytest.mark.parametrize(
        "field", ["current_location", "pickup_location", "dropoff_location"]
    )
    def test_a_missing_location_is_refused(self, api, route_stub, field):
        payload = {key: value for key, value in VALID.items() if key != field}
        response = api.post(
            "/api/v1/trips/", data=json.dumps(payload), content_type="application/json"
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_request"

    def test_a_blank_location_says_what_to_do(self, api, route_stub):
        response = post(api, current_location="")
        detail = response.json()["error"]["detail"]
        assert "Enter where the driver is now." in detail["current_location"]

    def test_negative_cycle_hours_are_refused(self, api, route_stub):
        assert post(api, current_cycle_used_hours=-1).status_code == 400

    def test_more_than_a_full_cycle_is_refused(self, api, route_stub):
        response = post(api, current_cycle_used_hours=80)
        assert response.status_code == 400
        assert "70" in json.dumps(response.json())

    def test_a_full_cycle_is_allowed(self, api, route_stub):
        # It means the driver has to restart before turning a wheel, which is
        # a real situation and a useful thing to be shown.
        assert post(api, current_cycle_used_hours=70).status_code == 201

    def test_an_unknown_place_explains_the_accepted_formats(self, api, route_stub):
        response = post(api, pickup_location="Zzzyx Nowhere Junction")
        assert response.status_code == 400
        error = response.json()["error"]
        assert error["code"] == "location_not_found"
        assert "Dallas, TX" in error["message"]

    def test_an_unknown_time_zone_is_refused(self, api, route_stub):
        response = post(api, timezone="Mars/Olympus_Mons")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "unknown_time_zone"

    def test_the_optional_fields_can_all_be_left_out(self, api, route_stub):
        response = api.post(
            "/api/v1/trips/",
            data=json.dumps({
                "current_location": "Chicago, IL",
                "pickup_location": "St. Louis, MO",
                "dropoff_location": "Dallas, TX",
                "current_cycle_used_hours": 0,
            }),
            content_type="application/json",
        )
        assert response.status_code == 201


# ==========================================================================
# When routing fails
# ==========================================================================


class TestRoutingFailures:
    @respx.mock
    def test_an_unreachable_provider_is_reported_as_unavailable(self, api, settings):
        settings.OSRM_FALLBACK_URL = ""
        respx.get(url__startswith=OSRM).mock(return_value=httpx.Response(503))
        response = post(api)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "routing_unavailable"

    @respx.mock
    def test_no_road_between_the_points_says_so(self, api, settings):
        settings.OSRM_FALLBACK_URL = ""
        respx.get(url__startswith=OSRM).mock(
            return_value=httpx.Response(200, json={"code": "NoRoute"})
        )
        response = post(api)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "route_not_found"

    @respx.mock
    def test_a_failed_trip_is_not_saved(self, api, settings):
        settings.OSRM_FALLBACK_URL = ""
        respx.get(url__startswith=OSRM).mock(return_value=httpx.Response(503))
        post(api)
        assert Trip.objects.count() == 0


# ==========================================================================
# Storage, retrieval and caching
# ==========================================================================


class TestPersistence:
    def test_a_planned_trip_is_kept(self, api, route_stub):
        body = post(api).json()
        assert Trip.objects.filter(pk=body["id"]).exists()

    def test_a_trip_can_be_fetched_again_by_id(self, api, route_stub):
        body = post(api).json()
        again = api.get(f"/api/v1/trips/{body['id']}/")
        assert again.status_code == 200
        assert again.json()["summary"] == body["summary"]

    def test_reloading_a_shared_link_costs_no_routing_call(self, api, route_stub):
        body = post(api).json()
        route_stub.reset()
        api.get(f"/api/v1/trips/{body['id']}/")
        assert route_stub.call_count == 0

    def test_an_unknown_trip_is_a_404(self, api):
        response = api.get("/api/v1/trips/2b3c4d5e-6f70-4182-9394-a5b6c7d8e9f0/")
        assert response.status_code == 404

    def test_the_same_request_twice_routes_once(self, api, route_stub):
        first = post(api).json()
        second = post(api).json()
        assert route_stub.call_count == 1
        assert first["id"] == second["id"]

    def test_a_different_request_routes_again(self, api, route_stub):
        post(api)
        post(api, current_cycle_used_hours=30.0)
        assert route_stub.call_count == 2


# ==========================================================================
# Metadata
# ==========================================================================


class TestMeta:
    def test_the_response_reports_what_it_cost(self, api, route_stub):
        meta = post(api).json()["meta"]
        assert meta["provider"] == "osrm"
        assert meta["api_calls"] == 1
        assert meta["computed_ms"] > 0

    def test_the_service_root_lists_the_endpoints(self, api):
        endpoints = api.get("/").json()["endpoints"]
        assert "plan_a_trip" in endpoints
        assert "retrieve_a_trip" in endpoints
