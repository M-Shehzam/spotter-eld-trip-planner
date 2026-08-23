"""Turn what a driver types into coordinates, and coordinates back into a name.

Everything here runs against ``data/us_places.csv``, a gazetteer of 27,093 US
populated places committed to the repository. Nothing in this module makes a
network call, which matters for three reasons: the autocomplete has to answer
on every keystroke, the planner names a dozen stops per trip, and a public
geocoder would rate-limit both.

Three operations:

``resolve``  free text or a coordinate pair -> a location
``suggest``  a prefix -> ranked completions for the autocomplete
``nearest``  a coordinate -> the closest town, for naming a stop

Adapted from the place resolver in spotter-fuel-route-api, with prefix search
and reverse lookup added.
"""

from __future__ import annotations

import csv
import logging
import re
from bisect import bisect_left
from dataclasses import dataclass

import numpy as np
from django.conf import settings

from apps.planner.errors import PlannerError
from apps.planner.geo import planar_miles

logger = logging.getLogger(__name__)


class LocationNotFound(PlannerError):
    """The text could not be matched to a place in the USA."""

    code = "location_not_found"


COORDINATE_PAIR = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*[,/ ]\s*(-?\d+(?:\.\d+)?)\s*$")

# Apostrophes are deleted rather than blanked, so "O'Neill" folds to ONEILL
# instead of splitting into two words.
_APOSTROPHE = re.compile(r"[’']")
_PUNCT = re.compile(r"[^A-Z0-9 ]+")
_SPACES = re.compile(r"\s+")

# Abbreviations people type that the gazetteer spells out.
_EXPANSIONS = {
    "ST": "SAINT",
    "STE": "SAINTE",
    "MT": "MOUNT",
    "FT": "FORT",
    "N": "NORTH",
    "S": "SOUTH",
    "E": "EAST",
    "W": "WEST",
    "NE": "NORTHEAST",
    "NW": "NORTHWEST",
    "SE": "SOUTHEAST",
    "SW": "SOUTHWEST",
    "HTS": "HEIGHTS",
    "JCT": "JUNCTION",
    "SPGS": "SPRINGS",
    "SPG": "SPRING",
    "CTR": "CENTER",
    "PT": "PORT",
}

STATE_NAMES = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
    "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE",
    "DISTRICT OF COLUMBIA": "DC", "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI",
    "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA",
    "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME",
    "MARYLAND": "MD", "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN",
    "MISSISSIPPI": "MS", "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE",
    "NEVADA": "NV", "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ", "NEW MEXICO": "NM",
    "NEW YORK": "NY", "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH",
    "OKLAHOMA": "OK", "OREGON": "OR", "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI",
    "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX",
    "UTAH": "UT", "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY",
}
STATE_CODES = frozenset(STATE_NAMES.values())

# Roughly the bounding box of the United States including Alaska and Hawaii.
US_BOUNDS = (18.0, 72.0, -180.0, -64.0)

# Grid cells for the reverse lookup, in degrees. One degree of latitude is
# about 69 miles, so a cell plus its eight neighbours covers every town within
# roughly 69 miles of the query point, which is further than any interstate
# stop is from a named place.
GRID_DEGREES = 1.0


def normalize(name: str) -> str:
    """Fold a place name to a comparable key."""
    folded = _PUNCT.sub(" ", _APOSTROPHE.sub("", (name or "").upper()))
    words = [_EXPANSIONS.get(word, word) for word in _SPACES.split(folded) if word]
    return " ".join(words)


@dataclass(frozen=True, slots=True)
class Place:
    name: str
    state: str
    latitude: float
    longitude: float
    population: int

    @property
    def label(self) -> str:
        return f"{self.name}, {self.state}"


@dataclass(slots=True)
class ResolvedLocation:
    latitude: float
    longitude: float
    label: str
    source: str  # "coordinates" or "gazetteer"
    query: str = ""

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "latitude": round(self.latitude, 6),
            "longitude": round(self.longitude, 6),
            "query": self.query,
            "source": self.source,
        }


class PlaceIndex:
    """The committed gazetteer, indexed three ways.

    Built once per process. Loading and indexing 27k rows takes about 340 ms,
    which is paid at start-up rather than on the first request.
    """

    def __init__(self) -> None:
        self._by_name_state: dict[tuple[str, str], Place] = {}
        self._by_name: dict[str, Place] = {}
        # Sorted (key, Place) pairs, so a prefix is a contiguous slice found by
        # bisect rather than a scan of every row.
        self._sorted_keys: list[str] = []
        self._sorted_places: list[Place] = []
        # Reverse lookup, bucketed on a one-degree grid.
        self._grid: dict[tuple[int, int], list[Place]] = {}

    @classmethod
    def load(cls, path=None) -> "PlaceIndex":
        path = path or settings.PLACES_CSV
        index = cls()
        pairs: list[tuple[str, Place]] = []

        with open(path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                state = row["state"].strip().upper()
                key = normalize(row["name"])
                if not key or not state:
                    continue

                place = Place(
                    name=row["name"].strip(),
                    state=state,
                    latitude=float(row["latitude"]),
                    longitude=float(row["longitude"]),
                    population=int(row["population"] or 0),
                )

                existing = index._by_name_state.get((key, state))
                if existing is None or place.population > existing.population:
                    index._by_name_state[(key, state)] = place

                # A bare city name resolves to the largest place of that name,
                # which is what someone typing "Springfield" almost always means.
                bare = index._by_name.get(key)
                if bare is None or place.population > bare.population:
                    index._by_name[key] = place

                pairs.append((key, place))
                index._grid.setdefault(_cell(place.latitude, place.longitude), []).append(place)

        pairs.sort(key=lambda pair: pair[0])
        index._sorted_keys = [key for key, _ in pairs]
        index._sorted_places = [place for _, place in pairs]
        return index

    # -- exact lookup ------------------------------------------------------

    def lookup(self, city: str, state: str | None) -> Place | None:
        key = normalize(city)
        if not key:
            return None
        if state:
            return self._by_name_state.get((key, state.upper()))
        return self._by_name.get(key)

    # -- prefix search -----------------------------------------------------

    def suggest(self, query: str, limit: int = 8) -> list[Place]:
        """Completions for a partial name, largest places first.

        A trailing state narrows the result, so "spring, tx" only offers Texas
        places. Without one, the biggest city wins, because a driver typing
        "dallas" means the one in Texas.
        """
        raw = (query or "").strip()
        if len(raw) < 2:
            return []

        city, state = split_state(raw)
        key = normalize(city)
        if not key:
            return []

        start = bisect_left(self._sorted_keys, key)
        matches: list[Place] = []
        seen: set[tuple[str, str]] = set()

        for position in range(start, len(self._sorted_keys)):
            if not self._sorted_keys[position].startswith(key):
                break
            place = self._sorted_places[position]
            if state and place.state != state:
                continue
            identity = (normalize(place.name), place.state)
            if identity in seen:
                continue
            seen.add(identity)
            matches.append(place)

        matches.sort(key=lambda place: (-place.population, place.name))
        return matches[:limit]

    # -- reverse lookup ----------------------------------------------------

    def nearest(self, latitude: float, longitude: float) -> Place | None:
        """The closest populated place, for naming a stop on the route.

        Searches outward one grid ring at a time and stops at the first ring
        that yields a candidate, so a stop in open country still gets a name.
        """
        centre = _cell(latitude, longitude)
        cosine = float(np.cos(np.radians(latitude)))

        for ring in range(0, 6):
            candidates: list[Place] = []
            for delta_lat in range(-ring, ring + 1):
                for delta_lon in range(-ring, ring + 1):
                    # Only the outermost shell is new on each pass.
                    if ring and max(abs(delta_lat), abs(delta_lon)) != ring:
                        continue
                    candidates.extend(
                        self._grid.get((centre[0] + delta_lat, centre[1] + delta_lon), ())
                    )

            if not candidates:
                continue

            latitudes = np.fromiter((p.latitude for p in candidates), dtype=np.float64)
            longitudes = np.fromiter((p.longitude for p in candidates), dtype=np.float64)
            distances = planar_miles(latitude, longitude, latitudes, longitudes, cosine)
            return candidates[int(np.argmin(distances))]

        return None

    def __len__(self) -> int:
        return len(self._sorted_places)


def _cell(latitude: float, longitude: float) -> tuple[int, int]:
    return (int(latitude // GRID_DEGREES), int(longitude // GRID_DEGREES))


_index: PlaceIndex | None = None


def get_index() -> PlaceIndex:
    global _index
    if _index is None:
        _index = PlaceIndex.load()
        logger.info("Place index loaded: %d places", len(_index))
    return _index


def reset_index() -> None:
    """Drop the cached index. Tests that point PLACES_CSV elsewhere need this."""
    global _index
    _index = None


def split_state(raw: str) -> tuple[str, str | None]:
    """Separate a trailing state from a place name.

    Handles "Dallas, TX", "Dallas, Texas", "Dallas TX" and "Dallas, Texas, USA".
    """
    text = raw.strip()

    if "," in text:
        city, _, tail = text.rpartition(",")
        folded = tail.strip().upper()
        if folded in STATE_CODES:
            return city.strip(), folded
        if folded in STATE_NAMES:
            return city.strip(), STATE_NAMES[folded]
        if folded in {"USA", "US", "UNITED STATES"}:
            return split_state(city.strip())
        return text, None

    words = text.split()
    if len(words) > 1 and words[-1].upper() in STATE_CODES:
        return " ".join(words[:-1]), words[-1].upper()

    return text, None


def resolve(text: str, *, index: PlaceIndex | None = None) -> ResolvedLocation:
    """Resolve free text or a coordinate pair to a location inside the USA."""
    raw = (text or "").strip()
    if not raw:
        raise LocationNotFound("A location is required.")

    coordinates = COORDINATE_PAIR.match(raw)
    if coordinates:
        latitude = float(coordinates.group(1))
        longitude = float(coordinates.group(2))
        _require_us(latitude, longitude, raw)
        index = index or get_index()
        near = index.nearest(latitude, longitude)
        return ResolvedLocation(
            latitude=latitude,
            longitude=longitude,
            label=near.label if near else f"{latitude:.4f}, {longitude:.4f}",
            source="coordinates",
            query=raw,
        )

    index = index or get_index()
    city, state = split_state(raw)
    place = index.lookup(city, state)

    if place is None:
        # Last resort: offer the best prefix match rather than failing on a
        # typed-but-incomplete name.
        candidates = index.suggest(raw, limit=1)
        place = candidates[0] if candidates else None

    if place is None:
        raise LocationNotFound(
            f"Could not find {raw!r} in the United States. Try a city and state "
            f"such as 'Dallas, TX', or coordinates such as '32.7767,-96.7970'.",
            detail={"query": raw},
        )

    return ResolvedLocation(
        latitude=place.latitude,
        longitude=place.longitude,
        label=place.label,
        source="gazetteer",
        query=raw,
    )


def _require_us(latitude: float, longitude: float, raw: str) -> None:
    if not -90.0 <= latitude <= 90.0 or not -180.0 <= longitude <= 180.0:
        raise LocationNotFound(f"{raw!r} is not a valid latitude and longitude.")

    south, north, west, east = US_BOUNDS
    if not (south <= latitude <= north and west <= longitude <= east):
        raise LocationNotFound(
            f"{latitude:.4f}, {longitude:.4f} is outside the United States. "
            "This planner covers routes within the USA."
        )
