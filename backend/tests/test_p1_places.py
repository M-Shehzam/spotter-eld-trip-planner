"""P1: the gazetteer resolves what a driver types, suggests, and names stops."""

import pytest

from apps.planner import places
from apps.planner.places import LocationNotFound


@pytest.fixture(scope="module")
def index():
    return places.get_index()


# -- loading ---------------------------------------------------------------


def test_index_covers_the_country(index):
    assert len(index) > 25_000


# -- resolving -------------------------------------------------------------


@pytest.mark.parametrize(
    "typed",
    ["Dallas, TX", "Dallas, Texas", "Dallas TX", "dallas, tx", "Dallas, Texas, USA"],
)
def test_a_city_and_state_resolve_however_it_is_written(index, typed):
    located = places.resolve(typed, index=index)
    assert located.label == "Dallas, TX"
    assert located.latitude == pytest.approx(32.78, abs=0.1)
    assert located.longitude == pytest.approx(-96.80, abs=0.1)


def test_a_bare_name_resolves_to_the_largest_place_of_that_name(index):
    assert places.resolve("Springfield", index=index).label.endswith(", MO")


def test_abbreviations_expand(index):
    assert places.resolve("St. Louis, MO", index=index).label == "Saint Louis, MO"


def test_coordinates_are_accepted_and_named(index):
    located = places.resolve("41.8781,-87.6298", index=index)
    assert located.source == "coordinates"
    assert located.latitude == pytest.approx(41.8781)
    assert "Chicago" in located.label


def test_a_place_outside_the_country_is_refused(index):
    with pytest.raises(LocationNotFound, match="outside the United States"):
        places.resolve("51.5074,-0.1278", index=index)


def test_an_unknown_place_explains_the_accepted_formats(index):
    with pytest.raises(LocationNotFound, match="Dallas, TX"):
        places.resolve("Zzzyx Nowhere Junction", index=index)


def test_an_empty_location_is_refused(index):
    with pytest.raises(LocationNotFound):
        places.resolve("   ", index=index)


# -- suggesting ------------------------------------------------------------


def test_suggestions_rank_the_largest_place_first(index):
    assert index.suggest("dall")[0].label == "Dallas, TX"


def test_a_trailing_state_narrows_the_suggestions(index):
    assert all(place.state == "TX" for place in index.suggest("spring, tx"))


def test_one_character_returns_nothing(index):
    assert index.suggest("d") == []


def test_suggestions_are_capped(index):
    assert len(index.suggest("s", limit=5)) <= 5


def test_the_same_place_is_not_offered_twice(index):
    labels = [place.label for place in index.suggest("chicago", limit=20)]
    assert len(labels) == len(set(labels))


# -- reverse lookup --------------------------------------------------------


def test_a_coordinate_finds_its_town(index):
    assert index.nearest(39.1200, -88.5434).name == "Effingham"


def test_open_country_still_gets_a_name(index):
    # Somewhere in the Nevada basin, far from any large town.
    assert index.nearest(39.5, -117.0) is not None


# -- endpoint --------------------------------------------------------------


def test_suggest_endpoint_returns_ranked_results(api):
    response = api.get("/api/v1/places/suggest/?q=dall")
    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["label"] == "Dallas, TX"
    assert body["results"][0]["state"] == "TX"


def test_suggest_endpoint_tolerates_a_short_query(api):
    assert api.get("/api/v1/places/suggest/?q=d").json()["results"] == []


def test_suggest_endpoint_tolerates_a_junk_limit(api):
    assert api.get("/api/v1/places/suggest/?q=dall&limit=banana").status_code == 200


def test_health_reports_the_index_size(api):
    assert api.get("/api/v1/health/").json()["places_indexed"] > 25_000
