"""P4: a continuous plan becomes one drawable sheet per calendar day."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from apps.planner.hos import (
    Drive,
    DutyStatus,
    Rules,
    StopKind,
    Work,
    build_itinerary,
    plan_trip,
)
from apps.planner.logsheet import HOURS_PER_DAY, build_log_sheets

SPEED = 55.0
CHICAGO = ZoneInfo("America/Chicago")
RULES = Rules()


def drive(miles: float, destination: str = "Somewhere, US") -> Drive:
    return Drive(miles=miles, hours=miles / SPEED, destination=destination)


def make_plan(*activities, cycle_used=0.0, start=None, rules=RULES):
    start = start or datetime(2026, 8, 24, 6, 0, tzinfo=CHICAGO)
    return plan_trip(
        list(activities),
        start=start,
        cycle_used_hours=cycle_used,
        rules=rules,
        locate=lambda mile: f"Mile {mile:.0f}, US",
    )


def sheets_for(*activities, cycle_used=0.0, start=None, origin="Chicago, IL", rules=RULES):
    plan = make_plan(*activities, cycle_used=cycle_used, start=start, rules=rules)
    return build_log_sheets(plan, zone=CHICAGO, origin_label=origin, rules=rules)


# ==========================================================================
# How many sheets, and for which days
# ==========================================================================


class TestSheetCount:
    def test_a_trip_inside_one_day_makes_one_sheet(self):
        sheets = sheets_for(drive(220))  # 06:00 to 10:00
        assert len(sheets) == 1
        assert sheets[0].date == date(2026, 8, 24)

    def test_a_trip_crossing_midnight_makes_two(self):
        # Starts 18:00, drives ten hours, so it ends at 04:00 the next day.
        sheets = sheets_for(
            drive(550), start=datetime(2026, 8, 24, 18, 0, tzinfo=CHICAGO)
        )
        assert [sheet.date for sheet in sheets] == [
            date(2026, 8, 24),
            date(2026, 8, 25),
        ]

    def test_a_long_haul_makes_a_sheet_for_every_day(self):
        sheets = sheets_for(drive(2400))
        assert len(sheets) >= 4
        # Consecutive, with no day missing in the middle.
        for earlier, later in zip(sheets, sheets[1:]):
            assert (later.date - earlier.date).days == 1

    def test_sheets_are_numbered_for_the_driver(self):
        sheets = sheets_for(drive(2400))
        assert [sheet.sheet_number for sheet in sheets] == list(
            range(1, len(sheets) + 1)
        )
        assert all(sheet.of == len(sheets) for sheet in sheets)


# ==========================================================================
# Every sheet accounts for all 24 hours
# ==========================================================================


TRIPS = [
    pytest.param((220, 0.0, 6), id="short-day"),
    pytest.param((550, 0.0, 18), id="crosses-midnight"),
    pytest.param((900, 0.0, 6), id="one-rest"),
    pytest.param((1400, 0.0, 22), id="fuel-and-rest-late-start"),
    pytest.param((2400, 0.0, 6), id="multi-day"),
    pytest.param((900, 68.0, 6), id="restart"),
    pytest.param((3000, 20.0, 13), id="long-afternoon-start"),
]


@pytest.fixture(params=TRIPS)
def any_sheets(request):
    miles, cycle_used, hour = request.param
    return sheets_for(
        *build_itinerary(
            miles_to_pickup=miles * 0.25,
            hours_to_pickup=miles * 0.25 / SPEED,
            pickup_label="Pickup, US",
            miles_to_dropoff=miles * 0.75,
            hours_to_dropoff=miles * 0.75 / SPEED,
            dropoff_label="Dropoff, US",
            rules=RULES,
        ),
        cycle_used=cycle_used,
        start=datetime(2026, 8, 24, hour, 0, tzinfo=CHICAGO),
    )


class TestEverySheetIsComplete:
    def test_the_totals_come_to_twenty_four_hours(self, any_sheets):
        for sheet in any_sheets:
            assert sum(sheet.totals.values()) == pytest.approx(HOURS_PER_DAY, abs=1e-6)
            assert sheet.is_complete

    def test_the_grid_runs_midnight_to_midnight(self, any_sheets):
        for sheet in any_sheets:
            assert sheet.entries[0].start_hour == pytest.approx(0.0)
            assert sheet.entries[-1].end_hour == pytest.approx(HOURS_PER_DAY)

    def test_the_grid_has_no_gaps(self, any_sheets):
        for sheet in any_sheets:
            for earlier, later in zip(sheet.entries, sheet.entries[1:]):
                assert later.start_hour == pytest.approx(earlier.end_hour)

    def test_no_two_neighbouring_runs_share_a_status(self, any_sheets):
        # Otherwise the drawn line would have an invisible seam in it.
        for sheet in any_sheets:
            for earlier, later in zip(sheet.entries, sheet.entries[1:]):
                assert earlier.status is not later.status

    def test_every_run_moves_forward(self, any_sheets):
        for sheet in any_sheets:
            assert all(entry.end_hour > entry.start_hour for entry in sheet.entries)

    def test_the_totals_match_the_grid(self, any_sheets):
        for sheet in any_sheets:
            for status in DutyStatus:
                drawn = sum(
                    entry.hours for entry in sheet.entries if entry.status is status
                )
                assert sheet.totals[status.value] == pytest.approx(drawn, abs=1e-3)


# ==========================================================================
# Cutting a segment at midnight
# ==========================================================================


class TestMidnightSplit:
    @pytest.fixture
    def overnight(self):
        # On duty at 18:00, driving until 04:00.
        return sheets_for(
            drive(550), start=datetime(2026, 8, 24, 18, 0, tzinfo=CHICAGO)
        )

    def test_the_first_day_ends_at_midnight(self, overnight):
        assert overnight[0].entries[-1].end_hour == pytest.approx(24.0)
        assert overnight[0].entries[-1].status is DutyStatus.DRIVING

    def test_the_second_day_starts_at_midnight(self, overnight):
        assert overnight[1].entries[0].start_hour == pytest.approx(0.0)
        assert overnight[1].entries[0].status is DutyStatus.DRIVING

    def test_the_driving_hours_split_across_the_two_days(self, overnight):
        assert overnight[0].totals["driving"] == pytest.approx(6.0)
        assert overnight[1].totals["driving"] == pytest.approx(4.0)

    def test_the_miles_split_in_the_same_proportion(self, overnight):
        assert overnight[0].total_miles_driving == pytest.approx(330.0, abs=0.5)
        assert overnight[1].total_miles_driving == pytest.approx(220.0, abs=0.5)

    def test_the_miles_add_up_to_the_route(self, overnight):
        assert sum(s.total_miles_driving for s in overnight) == pytest.approx(
            550.0, abs=0.5
        )

    def test_a_midnight_cut_is_not_recorded_as_a_change_of_status(self, overnight):
        # The driver did not do anything at midnight; the form did.
        assert not any(remark.hour == 0.0 for remark in overnight[1].remarks)


# ==========================================================================
# Padding the ends of the trip
# ==========================================================================


class TestPadding:
    def test_the_hours_before_departure_are_off_duty(self):
        sheets = sheets_for(drive(220))  # starts 06:00
        first = sheets[0].entries[0]
        assert first.status is DutyStatus.OFF_DUTY
        assert first.start_hour == pytest.approx(0.0)
        assert first.end_hour == pytest.approx(6.0)

    def test_the_hours_after_delivery_are_off_duty(self):
        sheets = sheets_for(drive(220))  # ends 10:00
        last = sheets[-1].entries[-1]
        assert last.status is DutyStatus.OFF_DUTY
        assert last.end_hour == pytest.approx(24.0)

    def test_a_day_spent_entirely_resting_is_still_a_full_sheet(self):
        # Two hours of cycle left and a 20:00 start, so the 34-hour restart
        # begins at 22:00 and swallows the whole of the following day.
        sheets = sheets_for(
            drive(900),
            cycle_used=68.0,
            start=datetime(2026, 8, 24, 20, 0, tzinfo=CHICAGO),
        )
        idle = [s for s in sheets if s.totals["off_duty"] == pytest.approx(24.0)]
        assert idle
        assert idle[0].is_complete
        # One unbroken off-duty run, drawn as a single line across the sheet.
        assert len(idle[0].entries) == 1


# ==========================================================================
# Where the day started and finished
# ==========================================================================


class TestFromAndTo:
    def test_the_first_sheet_starts_at_the_origin(self):
        sheets = sheets_for(drive(220), origin="Chicago, IL")
        assert sheets[0].from_label == "Chicago, IL"

    def test_each_sheet_picks_up_where_the_last_one_left_off(self):
        sheets = sheets_for(drive(2400))
        for earlier, later in zip(sheets, sheets[1:]):
            assert later.from_label == earlier.to_label

    def test_the_last_sheet_ends_at_the_destination(self):
        sheets = sheets_for(*build_itinerary(
            miles_to_pickup=110, hours_to_pickup=2.0, pickup_label="Pickup, IL",
            miles_to_dropoff=165, hours_to_dropoff=3.0, dropoff_label="Dallas, TX",
            rules=RULES,
        ))
        assert sheets[-1].to_label == "Dallas, TX"


# ==========================================================================
# Remarks
# ==========================================================================


class TestRemarks:
    def test_a_change_of_duty_status_is_recorded(self):
        sheets = sheets_for(*build_itinerary(
            miles_to_pickup=110, hours_to_pickup=2.0, pickup_label="Pickup, IL",
            miles_to_dropoff=165, hours_to_dropoff=3.0, dropoff_label="Dallas, TX",
            rules=RULES,
        ))
        kinds = [remark.kind for remark in sheets[0].remarks]
        assert StopKind.PICKUP in kinds
        assert StopKind.DROPOFF in kinds

    def test_each_remark_carries_a_place(self):
        sheets = sheets_for(drive(1400))
        for sheet in sheets:
            for remark in sheet.remarks:
                assert remark.location

    def test_the_first_remark_says_the_trip_began(self):
        sheets = sheets_for(drive(220))
        assert sheets[0].remarks[0].text == "Began trip"

    def test_a_remark_names_where_the_driver_was_not_where_they_are_headed(self):
        # The log records the place the change of duty status happened. A
        # driver leaving Newark writes Newark, not the city they will reach
        # eight hours later.
        plan = plan_trip(
            [drive(220, "Columbus, OH")],
            start=datetime(2026, 8, 24, 6, 0, tzinfo=CHICAGO),
            cycle_used_hours=0.0,
            rules=RULES,
            locate=lambda mile: f"Mile {mile:.0f}, US",
            origin_label="Newark, NJ",
        )
        sheets = build_log_sheets(
            plan, zone=CHICAGO, origin_label="Newark, NJ", rules=RULES
        )
        assert sheets[0].remarks[0].location == "Newark, NJ"

    def test_the_driver_gets_the_origin_they_typed(self):
        # Reverse lookup prefers the larger nearby place, which would turn
        # Newark into New York City. What the driver entered wins.
        plan = plan_trip(
            [drive(220)],
            start=datetime(2026, 8, 24, 6, 0, tzinfo=CHICAGO),
            cycle_used_hours=0.0,
            rules=RULES,
            locate=lambda mile: "New York City, NY",
            origin_label="Newark, NJ",
        )
        assert plan.segments[0].location == "Newark, NJ"

    def test_remarks_are_worded_for_a_driver_not_a_program(self):
        sheets = sheets_for(drive(1400))
        wordings = {remark.text for sheet in sheets for remark in sheet.remarks}
        assert "30-minute break" in wordings or "10-hour rest" in wordings
        assert not any("_" in wording for wording in wordings)

    def test_remarks_run_in_time_order(self):
        sheets = sheets_for(drive(2400))
        for sheet in sheets:
            hours = [remark.hour for remark in sheet.remarks]
            assert hours == sorted(hours)


# ==========================================================================
# The recap boxes
# ==========================================================================


class TestRecap:
    def test_todays_on_duty_hours_are_driving_plus_work(self):
        sheets = sheets_for(*build_itinerary(
            miles_to_pickup=110, hours_to_pickup=2.0, pickup_label="Pickup, IL",
            miles_to_dropoff=165, hours_to_dropoff=3.0, dropoff_label="Dropoff, MO",
            rules=RULES,
        ))
        # 2 hours driving, 1 loading, 3 driving, 1 unloading.
        assert sheets[0].recap.on_duty_today == pytest.approx(7.0)

    def test_box_a_carries_the_hours_the_driver_arrived_with(self):
        sheets = sheets_for(drive(110), cycle_used=42.0)  # two hours of driving
        assert sheets[0].recap.on_duty_last_8 == pytest.approx(44.0)

    def test_box_b_is_seventy_minus_box_a(self):
        sheets = sheets_for(drive(110), cycle_used=42.0)
        recap = sheets[0].recap
        assert recap.available_tomorrow == pytest.approx(70.0 - recap.on_duty_last_8)

    def test_box_b_never_goes_negative(self):
        sheets = sheets_for(
            Work(hours=1.0, kind=StopKind.PICKUP, location="Dock"), cycle_used=70.0
        )
        assert sheets[0].recap.available_tomorrow == 0.0

    def test_box_a_accumulates_across_sheets(self):
        sheets = sheets_for(drive(2400))
        totals = [sheet.recap.on_duty_last_8 for sheet in sheets]
        assert totals == sorted(totals)

    def test_a_restart_returns_box_a_to_the_hours_worked_since(self):
        sheets = sheets_for(drive(900), cycle_used=68.0)
        after_restart = [
            sheet
            for sheet in sheets
            if any(r.kind is StopKind.RESTART for r in sheet.remarks)
        ]
        assert after_restart
        # The cycle is cleared, so the last sheet is far below where it started.
        assert sheets[-1].recap.on_duty_last_8 < 68.0

    def test_box_c_stays_empty_when_it_cannot_be_known(self):
        # The driver gives one cycle figure with no day-by-day breakdown, so
        # for a short trip there is no honest way to fill the last-7-days box.
        sheets = sheets_for(drive(900))
        assert all(sheet.recap.on_duty_last_7 is None for sheet in sheets)


# ==========================================================================
# Time zones
# ==========================================================================


class TestHomeTerminalTime:
    def test_the_day_boundary_follows_the_home_terminal(self):
        # 23:00 Chicago on the 24th is 21:00 in Los Angeles on the same day,
        # so the same trip lands on different sheets depending on the zone.
        start = datetime(2026, 8, 24, 23, 0, tzinfo=CHICAGO)
        plan = make_plan(drive(165), start=start)  # three hours

        chicago = build_log_sheets(plan, zone=CHICAGO, origin_label="X", rules=RULES)
        pacific = build_log_sheets(
            plan, zone=ZoneInfo("America/Los_Angeles"), origin_label="X", rules=RULES
        )

        assert len(chicago) == 2  # crosses midnight in Chicago
        assert len(pacific) == 1  # 21:00 to 00:00 stays inside one Pacific day

    def test_totals_still_come_to_twenty_four_in_any_zone(self):
        plan = make_plan(drive(900))
        for name in ("America/New_York", "America/Denver", "Pacific/Honolulu"):
            sheets = build_log_sheets(
                plan, zone=ZoneInfo(name), origin_label="X", rules=RULES
            )
            for sheet in sheets:
                assert sum(sheet.totals.values()) == pytest.approx(24.0, abs=1e-6)


# ==========================================================================
# The whole set agrees with the plan it came from
# ==========================================================================


class TestAgreementWithThePlan:
    @pytest.fixture
    def plan_and_sheets(self):
        plan = make_plan(*build_itinerary(
            miles_to_pickup=300, hours_to_pickup=300 / SPEED, pickup_label="Pickup, MO",
            miles_to_dropoff=1800, hours_to_dropoff=1800 / SPEED, dropoff_label="Dropoff, CA",
            rules=RULES,
        ))
        return plan, build_log_sheets(
            plan, zone=CHICAGO, origin_label="Chicago, IL", rules=RULES
        )

    def test_the_sheets_carry_every_driving_hour(self, plan_and_sheets):
        plan, sheets = plan_and_sheets
        drawn = sum(sheet.totals["driving"] for sheet in sheets)
        assert drawn == pytest.approx(plan.driving_hours, abs=1e-3)

    def test_the_sheets_carry_every_mile(self, plan_and_sheets):
        plan, sheets = plan_and_sheets
        assert sum(s.total_miles_driving for s in sheets) == pytest.approx(
            plan.total_miles, abs=1.0
        )

    def test_the_sheets_carry_every_on_duty_hour(self, plan_and_sheets):
        plan, sheets = plan_and_sheets
        drawn = sum(
            sheet.totals["driving"] + sheet.totals["on_duty"] for sheet in sheets
        )
        assert drawn == pytest.approx(plan.on_duty_hours, abs=1e-3)

    def test_the_sheets_span_the_trip_and_nothing_more(self, plan_and_sheets):
        plan, sheets = plan_and_sheets
        assert sheets[0].date == plan.start.astimezone(CHICAGO).date()
        assert sheets[-1].date == plan.finish.astimezone(CHICAGO).date()
