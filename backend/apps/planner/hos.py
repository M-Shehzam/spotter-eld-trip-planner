"""Hours-of-service planning for a property-carrying driver.

This is the part of the app that has to be right. It takes an itinerary —
drive, load, drive, unload — and walks a clock forward through it, inserting
the breaks and rests that 49 CFR 395.3 requires, until the whole trip is
accounted for. What comes out is a flat list of duty segments covering every
minute from departure to delivery, which is exactly what a log sheet draws.

Nothing here touches the database, the network, or the gazetteer. Naming a
stop is a callable the caller supplies, so a test can pass ``lambda mile:
"somewhere"`` and check the arithmetic without a route.

Rules implemented
-----------------

11-hour driving limit
    No more than 11 hours driving after 10 consecutive hours off duty.

14-hour window
    No driving beyond the 14th hour after coming on duty. Off-duty time
    inside the window does not push it back, which is what makes a mid-day
    nap expensive and a full 10-hour reset the only real remedy.

30-minute break
    Required once 8 cumulative hours of driving have passed without one.
    Under the 2020 final rule any 30 consecutive minutes not driving
    qualifies, so the hour spent loading at the pickup satisfies it and no
    separate break is inserted. This is the rule most implementations get
    wrong, and it changes the shape of the first day.

70-hour / 8-day cycle
    No driving once 70 on-duty hours have accumulated. Seeded with the hours
    the driver reports having already used.

34-hour restart
    34 consecutive hours off duty returns the cycle to zero. Only inserted
    when the cycle is the binding constraint, because it costs a day and a
    half and no other limit is relieved by it.

Deliberately not modelled
-------------------------

The sleeper-berth split (8/2 and 7/3), the 16-hour short-haul exception, and
the adverse-driving-conditions extension. The brief rules out adverse
conditions, and for a single continuous dispatch the splits change how the
rest is drawn without changing when the truck arrives.

The 70 hours are treated as a running total rather than a true rolling
8-day window, because the driver's previous seven days are not among the
inputs. Only a 34-hour restart brings the total down. For trips of the length
this app plans, the two models agree.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from django.conf import settings

# Hours below this are rounding dust, not driving.
EPSILON = 1e-6


class DutyStatus(StrEnum):
    """The four rows of a driver's daily log, in the order they are printed."""

    OFF_DUTY = "off_duty"
    SLEEPER = "sleeper_berth"
    DRIVING = "driving"
    ON_DUTY = "on_duty"

    @property
    def row(self) -> int:
        return {
            DutyStatus.OFF_DUTY: 1,
            DutyStatus.SLEEPER: 2,
            DutyStatus.DRIVING: 3,
            DutyStatus.ON_DUTY: 4,
        }[self]

    @property
    def counts_as_on_duty(self) -> bool:
        """Whether the time accrues against the 70-hour cycle."""
        return self in {DutyStatus.DRIVING, DutyStatus.ON_DUTY}


class StopKind(StrEnum):
    """Why a segment exists. Drives the map marker and the remarks wording."""

    START = "start"
    DRIVE = "drive"
    PICKUP = "pickup"
    DROPOFF = "dropoff"
    FUEL = "fuel"
    BREAK = "break"
    REST = "rest"
    RESTART = "restart"


@dataclass(frozen=True, slots=True)
class Rules:
    """The regulation, in one place and overridable from the environment."""

    driving_limit_hours: float = 11.0
    duty_window_hours: float = 14.0
    driving_before_break_hours: float = 8.0
    break_hours: float = 0.5
    reset_hours: float = 10.0
    cycle_limit_hours: float = 70.0
    cycle_days: int = 8
    restart_hours: float = 34.0
    pickup_hours: float = 1.0
    dropoff_hours: float = 1.0
    fuel_interval_miles: float = 1000.0
    fuel_stop_hours: float = 0.5

    @classmethod
    def from_settings(cls) -> "Rules":
        return cls(
            driving_limit_hours=settings.HOS_DRIVING_LIMIT_HOURS,
            duty_window_hours=settings.HOS_DUTY_WINDOW_HOURS,
            driving_before_break_hours=settings.HOS_DRIVING_BEFORE_BREAK_HOURS,
            break_hours=settings.HOS_BREAK_HOURS,
            reset_hours=settings.HOS_RESET_HOURS,
            cycle_limit_hours=settings.HOS_CYCLE_LIMIT_HOURS,
            cycle_days=settings.HOS_CYCLE_DAYS,
            restart_hours=settings.HOS_RESTART_HOURS,
            pickup_hours=settings.PICKUP_HOURS,
            dropoff_hours=settings.DROPOFF_HOURS,
            fuel_interval_miles=settings.FUEL_INTERVAL_MILES,
            fuel_stop_hours=settings.FUEL_STOP_HOURS,
        )


# --------------------------------------------------------------------------
# Itinerary
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Drive:
    """A stretch of road between two waypoints."""

    miles: float
    hours: float
    destination: str

    @property
    def average_speed(self) -> float:
        return self.miles / self.hours if self.hours > EPSILON else 1.0


@dataclass(frozen=True, slots=True)
class Work:
    """Time on duty but not driving: loading, unloading."""

    hours: float
    kind: StopKind
    location: str


Activity = Drive | Work


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------


@dataclass(slots=True)
class Segment:
    """One unbroken stretch in a single duty status."""

    status: DutyStatus
    kind: StopKind
    start: datetime
    end: datetime
    label: str
    # Where the driver is when the segment begins, which is what the Remarks
    # column on a log sheet records. For anything but driving the two are the
    # same, because the truck has not moved.
    location: str
    end_location: str
    start_mile: float
    end_mile: float

    @property
    def hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600.0

    @property
    def miles(self) -> float:
        return self.end_mile - self.start_mile


@dataclass(slots=True)
class Plan:
    segments: list[Segment]
    start: datetime
    finish: datetime
    total_miles: float
    cycle_hours_at_start: float
    cycle_hours_at_finish: float
    violations: list[str] = field(default_factory=list)

    @property
    def elapsed_hours(self) -> float:
        return (self.finish - self.start).total_seconds() / 3600.0

    def hours_in(self, status: DutyStatus) -> float:
        return sum(s.hours for s in self.segments if s.status is status)

    @property
    def driving_hours(self) -> float:
        return self.hours_in(DutyStatus.DRIVING)

    @property
    def on_duty_hours(self) -> float:
        """Driving plus on-duty-not-driving, which is what the cycle counts."""
        return self.driving_hours + self.hours_in(DutyStatus.ON_DUTY)

    def count(self, kind: StopKind) -> int:
        return sum(1 for s in self.segments if s.kind is kind)


# --------------------------------------------------------------------------
# The simulator
# --------------------------------------------------------------------------


@dataclass(slots=True)
class _Clock:
    """Everything the regulation asks a driver to keep track of."""

    now: datetime
    mile: float = 0.0
    drive_since_reset: float = 0.0
    drive_since_break: float = 0.0
    cycle_used: float = 0.0
    miles_since_fuel: float = 0.0
    window_start: datetime | None = None

    def window_elapsed(self) -> float:
        if self.window_start is None:
            return 0.0
        return (self.now - self.window_start).total_seconds() / 3600.0


class _Planner:
    def __init__(
        self,
        rules: Rules,
        start: datetime,
        cycle_used: float,
        locate: Callable[[float], str],
        origin_label: str = "",
    ) -> None:
        self.rules = rules
        self.locate = locate
        self.origin_label = origin_label
        self.clock = _Clock(now=start, cycle_used=cycle_used, window_start=start)
        self.segments: list[Segment] = []
        self.start = start
        self.cycle_at_start = cycle_used

    # -- emitting ----------------------------------------------------------

    def _emit(
        self,
        status: DutyStatus,
        kind: StopKind,
        hours: float,
        label: str,
        miles: float = 0.0,
        location: str | None = None,
    ) -> None:
        if hours <= EPSILON:
            return

        began = self.clock.now
        start_mile = self.clock.mile
        self.clock.now = began + timedelta(hours=hours)
        self.clock.mile = start_mile + miles

        # A pickup or dropoff carries the name the driver typed, which beats
        # whatever the gazetteer would return for those coordinates. So does
        # the origin: someone who enters "Newark, NJ" should not be told their
        # trip began in New York City because it is the larger place nearby.
        # Everywhere else is named from where it happens on the route.
        if location is not None:
            where = location
        elif start_mile <= EPSILON and self.origin_label:
            where = self.origin_label
        else:
            where = self.locate(start_mile)
        ends_at = (
            location
            if location is not None
            else (where if miles <= EPSILON else self.locate(self.clock.mile))
        )

        self.segments.append(
            Segment(
                status=status,
                kind=kind,
                start=began,
                end=self.clock.now,
                label=label,
                location=where,
                end_location=ends_at,
                start_mile=start_mile,
                end_mile=self.clock.mile,
            )
        )

        if status is DutyStatus.DRIVING:
            self.clock.drive_since_reset += hours
            self.clock.drive_since_break += hours
            self.clock.cycle_used += hours
            self.clock.miles_since_fuel += miles
        else:
            if status is DutyStatus.ON_DUTY:
                self.clock.cycle_used += hours
            # Any half hour off the wheel clears the 30-minute break
            # requirement, whether it was taken as a break, spent loading, or
            # spent fuelling.
            if hours >= self.rules.break_hours - EPSILON:
                self.clock.drive_since_break = 0.0

    def _take_reset(self) -> None:
        """Ten hours off. Restores the driving limit and reopens the window."""
        self._emit(
            DutyStatus.SLEEPER,
            StopKind.REST,
            self.rules.reset_hours,
            f"{self.rules.reset_hours:g}-hour rest",
        )
        self.clock.drive_since_reset = 0.0
        self.clock.drive_since_break = 0.0
        self.clock.window_start = self.clock.now

    def _take_restart(self) -> None:
        """Thirty-four hours off. The only way to get the cycle back."""
        self._emit(
            DutyStatus.OFF_DUTY,
            StopKind.RESTART,
            self.rules.restart_hours,
            f"{self.rules.restart_hours:g}-hour restart",
        )
        self.clock.cycle_used = 0.0
        self.clock.drive_since_reset = 0.0
        self.clock.drive_since_break = 0.0
        self.clock.window_start = self.clock.now

    def _take_break(self) -> None:
        self._emit(
            DutyStatus.OFF_DUTY,
            StopKind.BREAK,
            self.rules.break_hours,
            f"{self.rules.break_hours * 60:g}-minute break",
        )

    def _take_fuel(self) -> None:
        self._emit(
            DutyStatus.ON_DUTY,
            StopKind.FUEL,
            self.rules.fuel_stop_hours,
            "Fuel",
        )
        self.clock.miles_since_fuel = 0.0

    # -- limits ------------------------------------------------------------

    def _drive_budget(self) -> float:
        """Hours the driver may legally drive right now, before any rest."""
        return min(
            self.rules.driving_limit_hours - self.clock.drive_since_reset,
            self.rules.duty_window_hours - self.clock.window_elapsed(),
            self.rules.driving_before_break_hours - self.clock.drive_since_break,
            self.rules.cycle_limit_hours - self.clock.cycle_used,
        )

    def _clear_the_way(self) -> None:
        """Rest until driving is legal again, cheapest remedy first.

        Order matters. A 30-minute break only relieves the break requirement,
        so it is useless when the driving limit or the window has run out; a
        10-hour reset relieves both of those but not the cycle; only the
        34-hour restart touches the cycle. Testing them from the most
        expensive downward picks the one that actually unblocks the driver.
        """
        for _ in range(8):  # a bound, so a bad rule set cannot spin forever
            if self._drive_budget() > EPSILON:
                return

            if self.clock.cycle_used >= self.rules.cycle_limit_hours - EPSILON:
                self._take_restart()
            elif (
                self.clock.drive_since_reset >= self.rules.driving_limit_hours - EPSILON
                or self.clock.window_elapsed() >= self.rules.duty_window_hours - EPSILON
            ):
                self._take_reset()
            else:
                self._take_break()

        raise RuntimeError("Could not find a rest that makes driving legal.")

    # -- activities --------------------------------------------------------

    def _drive(self, leg: Drive) -> None:
        remaining = leg.hours
        speed = leg.average_speed

        while remaining > EPSILON:
            self._clear_the_way()

            # A leg with no distance never needs fuel, and dividing by its
            # speed would be a division by zero.
            hours_to_fuel = (
                float("inf")
                if speed <= EPSILON
                else (self.rules.fuel_interval_miles - self.clock.miles_since_fuel) / speed
            )

            chunk = min(remaining, self._drive_budget(), hours_to_fuel)
            # Guard against a zero-length step when a limit lands exactly on a
            # boundary; the rest above has already been taken, so a hair of
            # progress is safe and keeps the loop moving.
            chunk = max(chunk, EPSILON * 10)
            chunk = min(chunk, remaining)

            self._emit(
                DutyStatus.DRIVING,
                StopKind.DRIVE,
                chunk,
                f"Driving to {leg.destination}",
                miles=chunk * speed,
            )
            remaining -= chunk

            needs_fuel = (
                self.clock.miles_since_fuel
                >= self.rules.fuel_interval_miles - EPSILON
            )
            if needs_fuel and remaining > EPSILON:
                self._take_fuel()

    def _work(self, task: Work) -> None:
        # Loading and unloading are on-duty work, not driving, so neither the
        # 14-hour window nor the cycle can stop them happening. They do accrue
        # against both, and the next drive pays for that.
        self._emit(
            DutyStatus.ON_DUTY,
            task.kind,
            task.hours,
            task.kind.value.capitalize(),
            location=task.location,
        )

    # -- entry point -------------------------------------------------------

    def run(self, activities: Sequence[Activity]) -> Plan:
        for activity in activities:
            if isinstance(activity, Drive):
                self._drive(activity)
            else:
                self._work(activity)

        plan = Plan(
            segments=self.segments,
            start=self.start,
            finish=self.clock.now,
            total_miles=self.clock.mile,
            cycle_hours_at_start=self.cycle_at_start,
            cycle_hours_at_finish=self.clock.cycle_used,
        )
        plan.violations = audit(plan, self.rules)
        return plan


def plan_trip(
    activities: Sequence[Activity],
    *,
    start: datetime,
    cycle_used_hours: float,
    rules: Rules | None = None,
    locate: Callable[[float], str] | None = None,
    origin_label: str = "",
) -> Plan:
    """Walk the itinerary forward, inserting every rest the rules require.

    Args:
        activities: Drives and on-duty work, in the order they happen.
        start: When the driver comes on duty. Assumed to follow at least 10
            consecutive hours off, so the driving limit and the 14-hour
            window both start fresh.
        cycle_used_hours: On-duty hours already spent in the current 8-day
            cycle. This is the one piece of history the driver supplies.
        rules: Defaults to the regulation as configured in settings.
        locate: Turns a mile marker into a place name for the remarks. A test
            can pass a stub.
        origin_label: What the driver called the starting point. Used in place
            of the gazetteer for mile zero.
    """
    rules = rules or Rules.from_settings()
    locate = locate or (lambda mile: "")
    return _Planner(rules, start, cycle_used_hours, locate, origin_label).run(activities)


def build_itinerary(
    *,
    miles_to_pickup: float,
    hours_to_pickup: float,
    pickup_label: str,
    miles_to_dropoff: float,
    hours_to_dropoff: float,
    dropoff_label: str,
    rules: Rules | None = None,
) -> list[Activity]:
    """The four activities of the trip described in the brief."""
    rules = rules or Rules.from_settings()
    return [
        Drive(miles=miles_to_pickup, hours=hours_to_pickup, destination=pickup_label),
        Work(hours=rules.pickup_hours, kind=StopKind.PICKUP, location=pickup_label),
        Drive(miles=miles_to_dropoff, hours=hours_to_dropoff, destination=dropoff_label),
        Work(hours=rules.dropoff_hours, kind=StopKind.DROPOFF, location=dropoff_label),
    ]


# --------------------------------------------------------------------------
# Audit
# --------------------------------------------------------------------------


def audit(plan: Plan, rules: Rules) -> list[str]:
    """Re-check a finished plan against the limits, independently of how it was built.

    The simulator decides where rests go; this walks the result and asks
    whether the regulation was actually met. Written deliberately as a second
    implementation rather than a reuse of the first, so a mistake in the
    planner shows up here instead of being confirmed by it. The app surfaces
    the result, so a plan that broke a rule says so rather than looking fine.
    """
    problems: list[str] = []

    drive_since_reset = 0.0
    drive_since_break = 0.0
    cycle_used = plan.cycle_hours_at_start
    window_start: datetime | None = plan.start

    for segment in plan.segments:
        if segment.status is DutyStatus.DRIVING:
            drive_since_reset += segment.hours
            drive_since_break += segment.hours
            cycle_used += segment.hours

            if drive_since_reset > rules.driving_limit_hours + 1e-4:
                problems.append(
                    f"{drive_since_reset:.2f} hours driving since the last 10-hour "
                    f"rest exceeds the {rules.driving_limit_hours:g}-hour limit "
                    f"(at {segment.end:%Y-%m-%d %H:%M})."
                )
            if drive_since_break > rules.driving_before_break_hours + 1e-4:
                problems.append(
                    f"{drive_since_break:.2f} hours driving without a "
                    f"{rules.break_hours * 60:g}-minute break exceeds the "
                    f"{rules.driving_before_break_hours:g}-hour limit "
                    f"(at {segment.end:%Y-%m-%d %H:%M})."
                )
            if cycle_used > rules.cycle_limit_hours + 1e-4:
                problems.append(
                    f"{cycle_used:.2f} on-duty hours exceeds the "
                    f"{rules.cycle_limit_hours:g}-hour cycle limit "
                    f"(at {segment.end:%Y-%m-%d %H:%M})."
                )
            if window_start is not None:
                elapsed = (segment.end - window_start).total_seconds() / 3600.0
                if elapsed > rules.duty_window_hours + 1e-4:
                    problems.append(
                        f"Driving {elapsed:.2f} hours into the duty window exceeds "
                        f"the {rules.duty_window_hours:g}-hour limit "
                        f"(at {segment.end:%Y-%m-%d %H:%M})."
                    )
        else:
            if segment.status is DutyStatus.ON_DUTY:
                cycle_used += segment.hours

            if segment.hours >= rules.reset_hours - 1e-4 and not segment.status.counts_as_on_duty:
                drive_since_reset = 0.0
                drive_since_break = 0.0
                window_start = segment.end
                if segment.hours >= rules.restart_hours - 1e-4:
                    cycle_used = 0.0
            elif segment.hours >= rules.break_hours - 1e-4:
                drive_since_break = 0.0

    covered = sum(segment.hours for segment in plan.segments)
    if abs(covered - plan.elapsed_hours) > 1e-4:
        problems.append(
            f"The segments cover {covered:.2f} hours but the trip spans "
            f"{plan.elapsed_hours:.2f}; the log would have a gap."
        )

    for earlier, later in zip(plan.segments, plan.segments[1:], strict=False):
        if earlier.end != later.start:
            problems.append(
                f"A gap or overlap between {earlier.label} and {later.label} "
                f"at {earlier.end:%Y-%m-%d %H:%M}."
            )
            break

    return problems
