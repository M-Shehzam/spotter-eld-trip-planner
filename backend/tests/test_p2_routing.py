"""P2: one call fetches the whole trip, and the result can be measured locally."""

import httpx
import pytest
import respx

from apps.planner import routing
from apps.planner.polyline import decode, encode
from apps.planner.routing import (
    Coordinate,
    OSRMProvider,
    RouteNotFound,
    RouteResult,
    RoutingUnavailable,
    fetch_route,
)

OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving/"


@pytest.fixture(autouse=True)
def _fresh_client():
    routing.reset_client()
    yield
    routing.reset_client()


def straight_line(start_lat, start_lon, end_lat, end_lon, points=60):
    """A polyline along a straight great-circle-ish path, for fixtures."""
    return [
        (
            start_lat + (end_lat - start_lat) * index / (points - 1),
            start_lon + (end_lon - start_lon) * index / (points - 1),
        )
        for index in range(points)
    ]


def osrm_payload(coordinates, leg_metres, leg_seconds):
    return {
        "code": "Ok",
        "routes": [
            {
                "geometry": encode(coordinates, precision=6),
                "distance": sum(leg_metres),
                "duration": sum(leg_seconds),
                "legs": [
                    {"distance": metres, "duration": seconds}
                    for metres, seconds in zip(leg_metres, leg_seconds)
                ],
            }
        ],
        "waypoints": [],
    }


# -- polyline codec --------------------------------------------------------


def test_the_codec_round_trips():
    points = [(41.8781, -87.6298), (38.6270, -90.1994), (32.7767, -96.7970)]
    assert decode(encode(points)) == pytest.approx(points, abs=1e-6)


def test_a_truncated_polyline_is_rejected():
    with pytest.raises(ValueError, match="Truncated"):
        decode("_p~iF~ps|U_")


# -- fetching --------------------------------------------------------------


@respx.mock
def test_one_request_covers_every_waypoint():
    coordinates = straight_line(41.88, -87.63, 32.78, -96.80)
    route = respx.get(url__startswith=OSRM_ROUTE_URL).mock(
        return_value=httpx.Response(
            200, json=osrm_payload(coordinates, [478_000, 1_200_000], [17_000, 43_000])
        )
    )

    result = OSRMProvider().route(
        [
            Coordinate(41.88, -87.63),
            Coordinate(38.63, -90.20),
            Coordinate(32.78, -96.80),
        ]
    )

    assert route.call_count == 1
    assert result.api_calls == 1
    # Three waypoints go out as one semicolon-joined path.
    assert result.point_count == len(coordinates)
    assert len(result.legs) == 2


@respx.mock
def test_legs_are_positioned_end_to_end_along_the_route():
    coordinates = straight_line(41.88, -87.63, 32.78, -96.80)
    respx.get(url__startswith=OSRM_ROUTE_URL).mock(
        return_value=httpx.Response(
            200, json=osrm_payload(coordinates, [482_803, 1_207_008], [17_000, 43_000])
        )
    )

    result = OSRMProvider().route([Coordinate(41.88, -87.63), Coordinate(32.78, -96.80)])

    first, second = result.legs
    assert first.start_mile == 0.0
    assert first.end_mile == pytest.approx(300.0, abs=0.5)
    assert second.start_mile == pytest.approx(first.end_mile)
    assert second.end_mile == pytest.approx(1050.0, abs=1.0)


@respx.mock
def test_no_route_is_reported_as_such():
    respx.get(url__startswith=OSRM_ROUTE_URL).mock(
        return_value=httpx.Response(200, json={"code": "NoRoute"})
    )
    with pytest.raises(RouteNotFound, match="No drivable route"):
        OSRMProvider().route([Coordinate(41.88, -87.63), Coordinate(21.31, -157.86)])


@respx.mock
def test_a_server_error_is_reported_as_unavailable():
    respx.get(url__startswith=OSRM_ROUTE_URL).mock(return_value=httpx.Response(502))
    with pytest.raises(RoutingUnavailable, match="502"):
        OSRMProvider().route([Coordinate(41.88, -87.63), Coordinate(32.78, -96.80)])


@respx.mock
def test_rate_limiting_is_reported_as_unavailable():
    respx.get(url__startswith=OSRM_ROUTE_URL).mock(return_value=httpx.Response(429))
    with pytest.raises(RoutingUnavailable, match="rate limiting"):
        OSRMProvider().route([Coordinate(41.88, -87.63), Coordinate(32.78, -96.80)])


@respx.mock
def test_a_definitive_answer_does_not_consult_the_standby(settings):
    settings.OSRM_FALLBACK_URL = "https://valhalla.example/"
    respx.get(url__startswith=OSRM_ROUTE_URL).mock(
        return_value=httpx.Response(200, json={"code": "NoRoute"})
    )
    standby = respx.post(url__startswith="https://valhalla.example/")

    with pytest.raises(RouteNotFound):
        fetch_route([Coordinate(41.88, -87.63), Coordinate(32.78, -96.80)])

    assert standby.call_count == 0


@respx.mock
def test_the_standby_covers_an_outage(settings):
    settings.OSRM_FALLBACK_URL = "https://valhalla.example"
    coordinates = straight_line(41.88, -87.63, 32.78, -96.80)
    respx.get(url__startswith=OSRM_ROUTE_URL).mock(return_value=httpx.Response(503))
    respx.post("https://valhalla.example/route").mock(
        return_value=httpx.Response(
            200,
            json={
                "trip": {
                    "summary": {"length": 967.0, "time": 60_000},
                    "legs": [
                        {
                            "shape": encode(coordinates, precision=6),
                            "summary": {"length": 967.0, "time": 60_000},
                        }
                    ],
                }
            },
        )
    )

    result = fetch_route([Coordinate(41.88, -87.63), Coordinate(32.78, -96.80)])

    assert result.provider == "valhalla"
    # Both attempts are reported, so the response never understates its egress.
    assert result.api_calls == 2


@respx.mock
def test_without_a_standby_the_outage_surfaces(settings):
    settings.OSRM_FALLBACK_URL = ""
    respx.get(url__startswith=OSRM_ROUTE_URL).mock(return_value=httpx.Response(503))
    with pytest.raises(RoutingUnavailable):
        fetch_route([Coordinate(41.88, -87.63), Coordinate(32.78, -96.80)])


# -- the distance profile --------------------------------------------------


@pytest.fixture
def chicago_to_dallas():
    coordinates = straight_line(41.88, -87.63, 32.78, -96.80, points=400)
    return RouteResult(
        coordinates=coordinates,
        distance_miles=1000.0,
        duration_hours=16.0,
        legs=[],
        provider="osrm",
    )


def test_the_profile_is_reconciled_with_the_reported_total(chicago_to_dallas):
    # Summed haversine hops and the provider's own total are made to agree, so
    # one number is authoritative everywhere.
    assert float(chicago_to_dallas.profile[-1]) == pytest.approx(1000.0)
    assert float(chicago_to_dallas.profile[0]) == 0.0


def test_the_profile_only_increases(chicago_to_dallas):
    import numpy as np

    assert np.all(np.diff(chicago_to_dallas.profile) >= 0)


@pytest.mark.parametrize("mile", [0.0, 1.0, 250.0, 500.0, 999.0, 1000.0])
def test_a_mile_marker_lands_on_the_route(chicago_to_dallas, mile):
    latitude, longitude = chicago_to_dallas.coordinate_at(mile)
    assert 32.0 <= latitude <= 42.0
    assert -97.0 <= longitude <= -87.0


def test_the_halfway_mark_is_halfway(chicago_to_dallas):
    latitude, longitude = chicago_to_dallas.coordinate_at(500.0)
    assert latitude == pytest.approx((41.88 + 32.78) / 2, abs=0.15)
    assert longitude == pytest.approx((-87.63 + -96.80) / 2, abs=0.15)


def test_mile_markers_beyond_the_route_clamp_to_its_ends(chicago_to_dallas):
    assert chicago_to_dallas.coordinate_at(-50.0) == chicago_to_dallas.coordinates[0]
    assert chicago_to_dallas.coordinate_at(9999.0) == chicago_to_dallas.coordinates[-1]


def test_the_bounding_box_covers_the_route(chicago_to_dallas):
    west, south, east, north = chicago_to_dallas.bbox()
    assert west < east and south < north
    assert south == pytest.approx(32.78, abs=0.01)
    assert north == pytest.approx(41.88, abs=0.01)


def test_geometry_sent_to_the_map_is_thinned(chicago_to_dallas):
    thinned = chicago_to_dallas.simplified(max_points=50)
    assert len(thinned) == 50
    # The ends are preserved, so the drawn line still reaches both cities.
    assert thinned[0] == chicago_to_dallas.coordinates[0]
    assert thinned[-1] == chicago_to_dallas.coordinates[-1]


def test_a_short_route_is_left_alone(chicago_to_dallas):
    assert chicago_to_dallas.simplified(max_points=10_000) is chicago_to_dallas.coordinates


# -- truck speed -----------------------------------------------------------


def test_the_provider_duration_is_used_as_planned_driving_time(chicago_to_dallas, settings):
    # OSRM's own estimate already implies a realistic truck average, so the
    # factor defaults to 1.0 and the duration passes through.
    settings.TRUCK_SPEED_FACTOR = 1.0
    assert routing.driving_hours(chicago_to_dallas, 16.0) == pytest.approx(16.0)


def test_the_factor_can_slow_the_plan_down(chicago_to_dallas, settings):
    settings.TRUCK_SPEED_FACTOR = 1.15
    assert routing.driving_hours(chicago_to_dallas, 16.0) == pytest.approx(18.4)


def test_a_truck_costed_duration_is_used_as_it_is(chicago_to_dallas, settings):
    settings.TRUCK_SPEED_FACTOR = 1.15
    chicago_to_dallas.provider = "valhalla"
    assert routing.driving_hours(chicago_to_dallas, 16.0) == 16.0
