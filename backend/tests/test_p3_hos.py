"""P3: the hours-of-service engine, one rule at a time.

Every expectation here is worked out by hand from 49 CFR 395.3 rather than
read off the implementation, so a change in behaviour shows up as a failure
instead of being absorbed.

The standing assumption in these tests is a driver averaging 55 mph, which
makes the arithmetic checkable: 11 hours of driving is 605 miles.
"""

from datetime import datetime, timedelta, timezone

import pytest

from apps.planner.hos import (
    Drive,
    DutyStatus,
    Plan,
    Rules,
    StopKind,
    Work,
    audit,
    build_itinerary,
    plan_trip,
)

SPEED = 55.0
START = datetime(2026, 8, 24, 6, 0, tzinfo=timezone.utc)
RULES = Rules()


def drive(miles: float, destination: str = "Somewhere, US") -> Drive:
    return Drive(miles=miles, hours=miles / SPEED, destination=destination)


def run(*activities, cycle_used: float = 0.0, rules: Rules = RULES, start=START) -> Plan:
    return plan_trip(
        list(activities),
        start=start,
        cycle_used_hours=cycle_used,
        rules=rules,
        locate=lambda mile: f"mile {mile:.0f}",
    )


def kinds(plan: Plan) -> list[str]:
    return [segment.kind.value for segment in plan.segments]


def statuses(plan: Plan) -> list[str]:
    return [segment.status.value for segment in plan.segments]


# ==========================================================================
# A trip that needs nothing
# ==========================================================================


class TestShortTrip:
    def test_a_short_run_inserts_no_rest(self):
        plan = run(drive(220))  # four hours
        assert kinds(plan) == ["drive"]
        assert plan.driving_hours == pytest.approx(4.0)

    def test_the_clock_advances_by_the_driving_time(self):
        plan = run(drive(220))
        assert plan.finish == START + timedelta(hours=4)

    def test_a_full_short_dispatch_is_drive_load_drive_unload(self):
        plan = run(*build_itinerary(
            miles_to_pickup=110, hours_to_pickup=2.0, pickup_label="Pickup, IL",
            miles_to_dropoff=165, hours_to_dropoff=3.0, dropoff_label="Dropoff, MO",
            rules=RULES,
        ))
        assert kinds(plan) == ["drive", "pickup", "drive", "dropoff"]
        # 2 driving + 1 loading + 3 driving + 1 unloading
        assert plan.elapsed_hours == pytest.approx(7.0)
        assert plan.on_duty_hours == pytest.approx(7.0)


# ==========================================================================
# 11-hour driving limit
# ==========================================================================


class TestDrivingLimit:
    def test_driving_stops_at_eleven_hours(self):
        # 900 miles is 16.4 hours of driving, well past the limit.
        plan = run(drive(900))
        first_stretch = [s for s in plan.segments if s.status is DutyStatus.DRIVING]
        before_rest = []
        for segment in plan.segments:
            if segment.kind is StopKind.REST:
                break
            if segment.status is DutyStatus.DRIVING:
                before_rest.append(segment)
        assert sum(s.hours for s in before_rest) == pytest.approx(11.0)
        assert len(first_stretch) > len(before_rest)

    def test_the_limit_is_relieved_by_ten_hours_off(self):
        plan = run(drive(900))
        rest = next(s for s in plan.segments if s.kind is StopKind.REST)
        assert rest.hours == pytest.approx(10.0)

    def test_a_ten_hour_rest_is_logged_in_the_sleeper_berth(self):
        # Which is where an over-the-road driver actually spends it.
        plan = run(drive(900))
        rest = next(s for s in plan.segments if s.kind is StopKind.REST)
        assert rest.status is DutyStatus.SLEEPER

    def test_driving_resumes_after_the_rest(self):
        plan = run(drive(900))
        after = plan.segments[plan.segments.index(
            next(s for s in plan.segments if s.kind is StopKind.REST)
        ) + 1:]
        assert any(s.status is DutyStatus.DRIVING for s in after)

    def test_total_driving_still_equals_the_route(self):
        plan = run(drive(900))
        assert plan.driving_hours == pytest.approx(900 / SPEED)
        assert plan.total_miles == pytest.approx(900)


# ==========================================================================
# 30-minute break after 8 hours driving
# ==========================================================================


class TestThirtyMinuteBreak:
    def test_a_break_is_required_after_eight_hours_driving(self):
        plan = run(drive(600))  # 10.9 hours, so the break lands but not a rest
        breaks = [s for s in plan.segments if s.kind is StopKind.BREAK]
        assert len(breaks) == 1
        assert breaks[0].hours == pytest.approx(0.5)

    def test_the_break_lands_exactly_at_eight_hours_of_driving(self):
        plan = run(drive(600))
        driven = 0.0
        for segment in plan.segments:
            if segment.kind is StopKind.BREAK:
                break
            if segment.status is DutyStatus.DRIVING:
                driven += segment.hours
        assert driven == pytest.approx(8.0)

    def test_a_short_run_needs_no_break(self):
        plan = run(drive(385))  # exactly 7 hours
        assert not any(s.kind is StopKind.BREAK for s in plan.segments)

    def test_the_break_is_logged_off_duty(self):
        plan = run(drive(600))
        assert next(s for s in plan.segments if s.kind is StopKind.BREAK).status is (
            DutyStatus.OFF_DUTY
        )

    def test_loading_satisfies_the_break(self):
        # The 2020 rule lets any 30 consecutive minutes off the wheel count.
        # Seven hours of driving, an hour loading, then four more hours: the
        # hour at the dock resets the break clock, so no separate break is
        # inserted even though 11 hours of driving happen in the day.
        plan = run(
            drive(385, "Dock"),                                   # 7.0 h
            Work(hours=1.0, kind=StopKind.PICKUP, location="Dock"),
            drive(220, "Delivery"),                               # 4.0 h
        )
        assert not any(s.kind is StopKind.BREAK for s in plan.segments)
        assert kinds(plan) == ["drive", "pickup", "drive"]

    def test_a_fuel_stop_also_satisfies_the_break(self):
        # Half an hour fuelling is exactly the qualifying interruption.
        plan = run(drive(1100))
        fuel_index = kinds(plan).index("fuel")
        driving_after_fuel = sum(
            s.hours for s in plan.segments[fuel_index:] if s.status is DutyStatus.DRIVING
        )
        assert driving_after_fuel > 0
        # No break in the eight hours of driving that follow the fuel stop.
        assert "break" not in kinds(plan)[fuel_index : fuel_index + 3]


# ==========================================================================
# 14-hour duty window
# ==========================================================================


class TestDutyWindow:
    def test_the_window_binds_when_enough_of_it_is_spent_not_driving(self):
        # A four-hour load leaves only ten hours of the window for driving,
        # which is less than the eleven the driving limit would allow.
        rules = Rules(pickup_hours=4.0)
        plan = run(
            drive(55, "Dock"),                                    # 1.0 h
            Work(hours=4.0, kind=StopKind.PICKUP, location="Dock"),
            drive(900, "Delivery"),
            rules=rules,
        )

        rest = next(s for s in plan.segments if s.kind is StopKind.REST)
        elapsed_at_rest = (rest.start - START).total_seconds() / 3600.0
        assert elapsed_at_rest == pytest.approx(14.0, abs=0.01)

        driving_before_rest = sum(
            s.hours
            for s in plan.segments[: plan.segments.index(rest)]
            if s.status is DutyStatus.DRIVING
        )
        # Stopped by the window, with driving hours still in hand.
        assert driving_before_rest < rules.driving_limit_hours
        assert driving_before_rest == pytest.approx(9.5, abs=0.01)

    def test_off_duty_time_does_not_push_the_window_back(self):
        # The 30-minute break is inside the window, so the driver still has to
        # park 14 hours after coming on duty, not 14.5.
        plan = run(drive(900))
        rest = next(s for s in plan.segments if s.kind is StopKind.REST)
        elapsed = (rest.start - START).total_seconds() / 3600.0
        assert elapsed == pytest.approx(11.5, abs=0.01)  # 11 driving + 0.5 break

    def test_the_window_reopens_after_a_ten_hour_rest(self):
        plan = run(drive(1500))
        rest = next(s for s in plan.segments if s.kind is StopKind.REST)
        after = [s for s in plan.segments if s.start >= rest.end]
        driving_after = sum(s.hours for s in after if s.status is DutyStatus.DRIVING)
        assert driving_after > 0


# ==========================================================================
# 70-hour / 8-day cycle and the 34-hour restart
# ==========================================================================


class TestCycle:
    def test_a_fresh_driver_needs_no_restart(self):
        plan = run(drive(600), cycle_used=0.0)
        assert not any(s.kind is StopKind.RESTART for s in plan.segments)

    def test_the_cycle_starts_where_the_driver_says_it_does(self):
        plan = run(drive(110), cycle_used=42.0)
        assert plan.cycle_hours_at_start == 42.0
        assert plan.cycle_hours_at_finish == pytest.approx(44.0)

    def test_a_nearly_exhausted_cycle_forces_a_restart(self):
        # Two hours left in the cycle, six hours of driving to do.
        plan = run(drive(330), cycle_used=68.0)
        restarts = [s for s in plan.segments if s.kind is StopKind.RESTART]
        assert len(restarts) == 1
        assert restarts[0].hours == pytest.approx(34.0)

    def test_the_driver_uses_the_last_of_the_cycle_before_restarting(self):
        plan = run(drive(330), cycle_used=68.0)
        restart = next(s for s in plan.segments if s.kind is StopKind.RESTART)
        driven_first = sum(
            s.hours
            for s in plan.segments[: plan.segments.index(restart)]
            if s.status is DutyStatus.DRIVING
        )
        assert driven_first == pytest.approx(2.0)

    def test_the_restart_clears_the_cycle(self):
        plan = run(drive(330), cycle_used=68.0)
        # 6 hours of driving in total, 2 before the restart and 4 after.
        assert plan.cycle_hours_at_finish == pytest.approx(4.0)

    def test_the_restart_is_logged_off_duty(self):
        plan = run(drive(330), cycle_used=68.0)
        assert next(s for s in plan.segments if s.kind is StopKind.RESTART).status is (
            DutyStatus.OFF_DUTY
        )

    def test_a_driver_with_no_hours_left_restarts_before_moving(self):
        plan = run(drive(110), cycle_used=70.0)
        assert plan.segments[0].kind is StopKind.RESTART

    def test_loading_still_happens_with_the_cycle_exhausted(self):
        # The regulation bars driving after 70 hours, not working.
        plan = run(
            Work(hours=1.0, kind=StopKind.PICKUP, location="Dock"),
            cycle_used=70.0,
        )
        assert kinds(plan) == ["pickup"]
        assert plan.cycle_hours_at_finish == pytest.approx(71.0)


# ==========================================================================
# Fuel
# ==========================================================================


class TestFuel:
    def test_a_trip_under_a_thousand_miles_needs_no_fuel_stop(self):
        plan = run(drive(900))
        assert not any(s.kind is StopKind.FUEL for s in plan.segments)

    def test_fuel_is_taken_at_the_thousand_mile_mark(self):
        plan = run(drive(1200))
        fuel = next(s for s in plan.segments if s.kind is StopKind.FUEL)
        assert fuel.start_mile == pytest.approx(1000.0, abs=0.5)

    def test_a_long_trip_fuels_every_thousand_miles(self):
        plan = run(drive(2400))
        fuel_stops = [s for s in plan.segments if s.kind is StopKind.FUEL]
        assert [round(s.start_mile) for s in fuel_stops] == [1000, 2000]

    def test_fuelling_is_on_duty_not_driving(self):
        plan = run(drive(1200))
        fuel = next(s for s in plan.segments if s.kind is StopKind.FUEL)
        assert fuel.status is DutyStatus.ON_DUTY
        assert fuel.hours == pytest.approx(0.5)

    def test_no_fuel_stop_is_appended_at_the_very_end(self):
        # Exactly a thousand miles arrives on empty, but there is nowhere left
        # to go, so parking at the delivery beats fuelling in the yard.
        plan = run(drive(1000))
        assert not any(s.kind is StopKind.FUEL for s in plan.segments)


# ==========================================================================
# The pieces working together
# ==========================================================================


class TestWholeTrips:
    @pytest.fixture
    def long_haul(self):
        return run(*build_itinerary(
            miles_to_pickup=300, hours_to_pickup=300 / SPEED, pickup_label="Pickup, MO",
            miles_to_dropoff=1800, hours_to_dropoff=1800 / SPEED, dropoff_label="Dropoff, CA",
            rules=RULES,
        ))

    def test_the_route_is_driven_in_full(self, long_haul):
        assert long_haul.total_miles == pytest.approx(2100)
        assert long_haul.driving_hours == pytest.approx(2100 / SPEED)

    def test_loading_and_unloading_both_happen(self, long_haul):
        assert long_haul.count(StopKind.PICKUP) == 1
        assert long_haul.count(StopKind.DROPOFF) == 1

    def test_the_trip_spans_several_days(self, long_haul):
        assert long_haul.elapsed_hours > 48

    def test_nothing_in_the_plan_breaks_a_rule(self, long_haul):
        assert long_haul.violations == []


# ==========================================================================
# Invariants that must hold for any trip at all
# ==========================================================================


CASES = [
    pytest.param((120, 0.0), id="short-trip"),
    pytest.param((600, 0.0), id="one-break"),
    pytest.param((900, 0.0), id="one-rest"),
    pytest.param((1400, 0.0), id="fuel-and-rest"),
    pytest.param((2400, 0.0), id="multi-day"),
    pytest.param((3200, 12.0), id="long-with-hours-used"),
    pytest.param((900, 68.0), id="restart-needed"),
    pytest.param((1800, 69.5), id="restart-then-more"),
    pytest.param((40, 70.0), id="cycle-exhausted"),
]


@pytest.fixture(params=CASES)
def any_trip(request) -> Plan:
    miles, cycle_used = request.param
    return run(*build_itinerary(
        miles_to_pickup=miles * 0.2,
        hours_to_pickup=miles * 0.2 / SPEED,
        pickup_label="Pickup",
        miles_to_dropoff=miles * 0.8,
        hours_to_dropoff=miles * 0.8 / SPEED,
        dropoff_label="Dropoff",
        rules=RULES,
    ), cycle_used=cycle_used)


class TestInvariants:
    def test_the_log_has_no_gaps(self, any_trip):
        for earlier, later in zip(any_trip.segments, any_trip.segments[1:]):
            assert earlier.end == later.start

    def test_every_minute_is_accounted_for(self, any_trip):
        covered = sum(segment.hours for segment in any_trip.segments)
        assert covered == pytest.approx(any_trip.elapsed_hours, abs=1e-6)

    def test_the_four_duty_statuses_sum_to_the_elapsed_time(self, any_trip):
        total = sum(any_trip.hours_in(status) for status in DutyStatus)
        assert total == pytest.approx(any_trip.elapsed_hours, abs=1e-6)

    def test_no_segment_runs_backwards(self, any_trip):
        assert all(segment.end > segment.start for segment in any_trip.segments)

    def test_mileage_only_increases(self, any_trip):
        for earlier, later in zip(any_trip.segments, any_trip.segments[1:]):
            assert later.start_mile == pytest.approx(earlier.end_mile)

    def test_only_driving_covers_ground(self, any_trip):
        for segment in any_trip.segments:
            if segment.status is not DutyStatus.DRIVING:
                assert segment.miles == pytest.approx(0.0)

    def test_the_plan_audits_clean(self, any_trip):
        assert any_trip.violations == []

    def test_the_audit_agrees_with_the_planner(self, any_trip):
        # The audit is a second implementation of the limits, so a planner
        # bug shows up here rather than being confirmed by its own logic.
        assert audit(any_trip, RULES) == []


# ==========================================================================
# The audit itself
# ==========================================================================


class TestAudit:
    def test_it_catches_driving_past_the_eleven_hour_limit(self):
        plan = run(drive(220))
        # Stretch the single driving segment to twelve hours.
        plan.segments[0].end = plan.segments[0].start + timedelta(hours=12)
        plan.finish = plan.segments[0].end
        problems = audit(plan, RULES)
        assert any("11-hour limit" in problem for problem in problems)

    def test_it_catches_driving_past_the_eight_hour_break_point(self):
        plan = run(drive(220))
        plan.segments[0].end = plan.segments[0].start + timedelta(hours=9)
        plan.finish = plan.segments[0].end
        assert any("30-minute break" in problem for problem in audit(plan, RULES))

    def test_it_catches_a_gap_in_the_log(self):
        plan = run(drive(600))
        plan.segments[1].start += timedelta(minutes=15)
        assert any("gap or overlap" in problem for problem in audit(plan, RULES))

    def test_it_catches_an_overrun_cycle(self):
        # The planner would have inserted a restart here, so the plan has to
        # be tampered with to produce the violation: four hours of driving
        # backdated onto a cycle that only had one hour left in it.
        plan = run(drive(220))
        plan.cycle_hours_at_start = 69.0
        assert any("cycle limit" in problem for problem in audit(plan, RULES))

    def test_a_plan_the_engine_produced_never_overruns_the_cycle(self):
        plan = run(drive(220), cycle_used=69.0)
        assert plan.violations == []
        assert any(s.kind is StopKind.RESTART for s in plan.segments)


# ==========================================================================
# Configuration
# ==========================================================================


class TestRulesFromSettings:
    def test_the_defaults_are_the_regulation(self, settings):
        rules = Rules.from_settings()
        assert rules.driving_limit_hours == 11.0
        assert rules.duty_window_hours == 14.0
        assert rules.driving_before_break_hours == 8.0
        assert rules.cycle_limit_hours == 70.0
        assert rules.restart_hours == 34.0

    def test_the_brief_assumptions_are_the_defaults(self, settings):
        rules = Rules.from_settings()
        assert rules.pickup_hours == 1.0
        assert rules.dropoff_hours == 1.0
        assert rules.fuel_interval_miles == 1000.0

    def test_a_limit_can_be_changed_without_touching_code(self, settings):
        settings.HOS_DRIVING_LIMIT_HOURS = 10.0
        assert Rules.from_settings().driving_limit_hours == 10.0
