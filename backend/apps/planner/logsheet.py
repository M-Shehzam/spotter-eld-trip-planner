"""Turn a plan into the daily log sheets that get drawn.

The engine produces one continuous list of duty segments. A driver's daily
log is a 24-hour grid, midnight to midnight in the time standard of the home
terminal, so a trip of any length becomes several sheets and any segment that
crosses midnight has to be cut in two.

What this module works out, per sheet:

grid entries
    Runs of a single duty status, positioned as hours from midnight, which is
    all the drawing needs to step the line across the four rows.

totals
    Hours in each of the four statuses. They sum to 24 on every sheet,
    because a log with a gap is not a log.

miles
    Driving distance for that calendar day, split proportionally where a
    driving segment crosses midnight.

remarks
    The place and time of every change of duty status, which is what the
    Remarks box on the form is for.

recap
    The 70-hour / 8-day boxes at the bottom of the form.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from apps.planner.hos import DutyStatus, Plan, Rules, Segment, StopKind

HOURS_PER_DAY = 24.0

# Wording for the Remarks column. A driver writes where the change happened
# and what it was, not the internal name of the event.
REMARK_WORDING = {
    StopKind.DRIVE: "Driving",
    StopKind.PICKUP: "Pickup, loading",
    StopKind.DROPOFF: "Dropoff, unloading",
    StopKind.FUEL: "Fuel stop",
    StopKind.BREAK: "30-minute break",
    StopKind.REST: "10-hour rest",
    StopKind.RESTART: "34-hour restart",
    StopKind.START: "Began trip",
}


@dataclass(slots=True)
class GridEntry:
    """A run of one duty status inside a single day."""

    status: DutyStatus
    start_hour: float
    end_hour: float

    @property
    def hours(self) -> float:
        return self.end_hour - self.start_hour


@dataclass(slots=True)
class Remark:
    hour: float
    text: str
    location: str
    kind: StopKind


@dataclass(slots=True)
class Recap:
    """The 70-hour / 8-day boxes.

    ``on_duty_last_8`` is box A, ``available_tomorrow`` is box B, and
    ``on_duty_last_7`` is box C.

    Box C cannot be filled honestly from the inputs this app is given. The
    driver supplies one number, the hours already used in the cycle, with no
    day-by-day breakdown, so there is no way to know how many of them fall on
    the eighth day back. It stays None until the trip itself has run long
    enough for the answer to come from the plan rather than a guess. Printing
    an invented figure on a federal form is worse than leaving the box empty.
    """

    on_duty_today: float
    on_duty_last_8: float
    available_tomorrow: float
    on_duty_last_7: float | None = None


@dataclass(slots=True)
class LogSheet:
    date: date
    sheet_number: int
    of: int
    from_label: str
    to_label: str
    total_miles_driving: float
    total_mileage: float
    entries: list[GridEntry]
    remarks: list[Remark]
    totals: dict[str, float]
    recap: Recap

    @property
    def is_complete(self) -> bool:
        """A sheet has to account for all 24 hours."""
        return abs(sum(self.totals.values()) - HOURS_PER_DAY) < 1e-6


@dataclass(slots=True)
class _Piece:
    """A segment, or the part of one that falls inside a single day."""

    status: DutyStatus
    kind: StopKind
    start_hour: float
    end_hour: float
    miles: float
    location: str
    end_location: str
    starts_segment: bool
    ends_segment: bool

    @property
    def hours(self) -> float:
        return self.end_hour - self.start_hour


def _slice_into_days(
    segments: list[Segment], zone: ZoneInfo
) -> dict[date, list[_Piece]]:
    """Cut every segment at local midnight and file the parts by date."""
    by_day: dict[date, list[_Piece]] = {}

    for segment in segments:
        start = segment.start.astimezone(zone)
        finish = segment.end.astimezone(zone)
        total_seconds = (finish - start).total_seconds()

        cursor = start
        while cursor < finish:
            day = cursor.date()
            midnight = datetime.combine(
                day + timedelta(days=1), datetime.min.time(), tzinfo=zone
            )
            piece_end = min(finish, midnight)

            day_start = datetime.combine(day, datetime.min.time(), tzinfo=zone)
            start_hour = (cursor - day_start).total_seconds() / 3600.0
            end_hour = (piece_end - day_start).total_seconds() / 3600.0

            share = (
                (piece_end - cursor).total_seconds() / total_seconds
                if total_seconds > 0
                else 0.0
            )

            by_day.setdefault(day, []).append(
                _Piece(
                    status=segment.status,
                    kind=segment.kind,
                    start_hour=start_hour,
                    end_hour=end_hour,
                    miles=segment.miles * share,
                    location=segment.location,
                    end_location=segment.end_location,
                    starts_segment=cursor == start,
                    ends_segment=piece_end == finish,
                )
            )
            cursor = piece_end

    return by_day


def _pad_to_full_day(pieces: list[_Piece]) -> list[_Piece]:
    """Fill the hours before the first and after the last piece as off duty.

    Only the first and last sheets of a trip need this. The driver was not
    working before the dispatch began or after it ended, and the form has no
    way to say "nothing recorded".
    """
    padded: list[_Piece] = []

    if not pieces:
        return [
            _Piece(
                status=DutyStatus.OFF_DUTY,
                kind=StopKind.START,
                start_hour=0.0,
                end_hour=HOURS_PER_DAY,
                miles=0.0,
                location="",
                end_location="",
                starts_segment=False,
                ends_segment=False,
            )
        ]

    if pieces[0].start_hour > 1e-9:
        padded.append(
            _Piece(
                status=DutyStatus.OFF_DUTY,
                kind=StopKind.START,
                start_hour=0.0,
                end_hour=pieces[0].start_hour,
                miles=0.0,
                location="",
                end_location="",
                starts_segment=False,
                ends_segment=False,
            )
        )

    padded.extend(pieces)

    if pieces[-1].end_hour < HOURS_PER_DAY - 1e-9:
        padded.append(
            _Piece(
                status=DutyStatus.OFF_DUTY,
                kind=StopKind.START,
                start_hour=pieces[-1].end_hour,
                end_hour=HOURS_PER_DAY,
                miles=0.0,
                location="",
                end_location="",
                starts_segment=False,
                ends_segment=False,
            )
        )

    return padded


def _merge(pieces: list[_Piece]) -> list[GridEntry]:
    """Collapse consecutive pieces sharing a duty status into one run.

    The line drawn on the grid only changes when the status does, so a fuel
    stop that runs straight into loading is one horizontal stroke on the
    on-duty row rather than two.
    """
    entries: list[GridEntry] = []

    for piece in pieces:
        if entries and entries[-1].status is piece.status:
            entries[-1].end_hour = piece.end_hour
        else:
            entries.append(
                GridEntry(
                    status=piece.status,
                    start_hour=piece.start_hour,
                    end_hour=piece.end_hour,
                )
            )

    return entries


def _totals(entries: list[GridEntry]) -> dict[str, float]:
    totals = {status.value: 0.0 for status in DutyStatus}
    for entry in entries:
        totals[entry.status.value] += entry.hours
    return {name: round(hours, 4) for name, hours in totals.items()}


def _remarks(pieces: list[_Piece], is_first_sheet: bool) -> list[Remark]:
    """One entry per change of duty status, with the place it happened."""
    remarks: list[Remark] = []

    for piece in pieces:
        if not piece.location:
            continue

        # A segment cut by midnight is not a change of status; it continues.
        if not piece.starts_segment:
            continue

        text = REMARK_WORDING.get(piece.kind, piece.kind.value.capitalize())
        # The opening entry on the first sheet is the driver going on duty,
        # not merely another stretch of driving.
        if not remarks and is_first_sheet and piece.kind is StopKind.DRIVE:
            text = "Began trip"

        remarks.append(
            Remark(
                hour=piece.start_hour,
                text=text,
                location=piece.location,
                kind=piece.kind,
            )
        )

    return remarks


def build_log_sheets(
    plan: Plan,
    *,
    zone: ZoneInfo,
    origin_label: str,
    rules: Rules | None = None,
) -> list[LogSheet]:
    """One sheet per calendar day the trip touches, in order."""
    rules = rules or Rules.from_settings()
    by_day = _slice_into_days(plan.segments, zone)
    days = sorted(by_day)

    # The 70-hour cycle runs across sheets, so it is tracked here rather than
    # recomputed per day. A restart zeroes it at the moment it completes.
    cycle = plan.cycle_hours_at_start
    trip_on_duty_by_day: dict[date, float] = {}
    cycle_by_day: dict[date, float] = {}

    for day in days:
        on_duty_today = 0.0
        for piece in by_day[day]:
            if piece.kind is StopKind.RESTART and piece.ends_segment:
                cycle = 0.0
            elif piece.status.counts_as_on_duty:
                cycle += piece.hours
                on_duty_today += piece.hours
        trip_on_duty_by_day[day] = on_duty_today
        cycle_by_day[day] = cycle

    sheets: list[LogSheet] = []
    previous_location = origin_label

    for index, day in enumerate(days):
        pieces = by_day[day]
        padded = _pad_to_full_day(pieces)
        entries = _merge(padded)

        # Where the driver actually finished the day, which for a day that
        # ends mid-drive is the point on the road at midnight rather than the
        # city that stretch was headed for.
        ended_at = [piece.end_location for piece in pieces if piece.end_location]
        from_label = previous_location
        to_label = ended_at[-1] if ended_at else previous_location
        previous_location = to_label

        driving_miles = sum(
            piece.miles for piece in pieces if piece.status is DutyStatus.DRIVING
        )

        on_duty_last_8 = cycle_by_day[day]
        recap = Recap(
            on_duty_today=round(trip_on_duty_by_day[day], 4),
            on_duty_last_8=round(on_duty_last_8, 4),
            available_tomorrow=round(
                max(rules.cycle_limit_hours - on_duty_last_8, 0.0), 4
            ),
            on_duty_last_7=_seven_day_total(
                days, index, trip_on_duty_by_day, cycle_by_day, plan
            ),
        )

        sheets.append(
            LogSheet(
                date=day,
                sheet_number=index + 1,
                of=len(days),
                from_label=from_label,
                to_label=to_label,
                total_miles_driving=round(driving_miles, 1),
                total_mileage=round(driving_miles, 1),
                entries=entries,
                remarks=_remarks(padded, is_first_sheet=index == 0),
                totals=_totals(entries),
                recap=recap,
            )
        )

    return sheets


def _seven_day_total(
    days: list[date],
    index: int,
    on_duty_by_day: dict[date, float],
    cycle_by_day: dict[date, float],
    plan: Plan,
) -> float | None:
    """Box C: on-duty hours in the last 7 days including today.

    Derivable only once the trip has supplied eight days of its own history.
    Before that the answer depends on how the driver's entering hours were
    spread across the days before departure, which is not something the app
    is told. Returning None leaves the box blank rather than filling a
    federal form with a number that was guessed.
    """
    if index < 7:
        return None

    eighth_day_back = days[index - 7]
    return round(cycle_by_day[days[index]] - on_duty_by_day[eighth_day_back], 4)
