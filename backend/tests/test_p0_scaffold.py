"""P0: the project boots, the settings load, and the probe answers."""

import pytest


def test_health_reports_ok(api):
    response = api.get("/api/v1/health/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_service_root_describes_the_service(api):
    response = api.get("/")
    assert response.status_code == 200
    assert "endpoints" in response.json()


@pytest.mark.django_db
def test_trip_table_exists():
    from apps.planner.models import Trip

    assert Trip.objects.count() == 0


def test_hos_limits_match_the_regulation(settings):
    assert settings.HOS_DRIVING_LIMIT_HOURS == 11.0
    assert settings.HOS_DUTY_WINDOW_HOURS == 14.0
    assert settings.HOS_CYCLE_LIMIT_HOURS == 70.0
    assert settings.HOS_RESTART_HOURS == 34.0
