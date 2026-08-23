"""Rebuild ``data/us_places.csv`` from the GeoNames US dump.

The committed CSV is what the app ships with, so this command exists to make
that file reproducible rather than to be run at deploy time.

    curl -O https://download.geonames.org/export/dump/US.zip
    unzip US.zip
    python manage.py build_places --source US.txt

One row per GeoNames record, under its canonical name only. The alternate
names column is deliberately discarded: it carries transliterations
("Cekaga", "sheng ta ke la li ta") and airport codes ("CHI", "DFW") that sit
on the same coordinates and carry the same population as the real city. Kept,
they win the reverse lookup and a log sheet ends up reading "DFW, TX" where
a driver would have written "Dallas, TX".
"""

from __future__ import annotations

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

# Column positions in the GeoNames tab-separated export.
COL_NAME = 1
COL_LATITUDE = 4
COL_LONGITUDE = 5
COL_FEATURE_CLASS = 6
COL_FEATURE_CODE = 7
COL_STATE = 10
COL_POPULATION = 14

# Class P is populated places: cities, towns and villages.
POPULATED_CLASS = "P"

# GeoNames records 138,000 US places with no population figure: unincorporated
# crossroads, ghost settlements, named clusters of a few houses. They are
# five sixths of the file and they make the app worse, not better. The reverse
# lookup exists to write a name a driver would recognise in the remarks
# column, and an unnamed crossroads is the opposite of that. Excluding them
# takes the gazetteer from 6.0 MB to 1.2 MB and start-up from 2.4 s to 0.4 s.
#
# What is lost is the ability to resolve a hamlet typed by name. ``resolve``
# already falls back to the closest prefix match and accepts raw coordinates,
# so that case degrades rather than fails.
DEFAULT_MIN_POPULATION = 1

# Places that no longer exist. A route never stops in one, and leaving them
# in lets a ghost town outrank the living city of the same name.
HISTORICAL_CODES = frozenset({"PPLQ", "PPLW", "PPLH", "PPLCH"})

# Sections of a larger place: neighbourhoods, subdivisions, districts. A
# driver writes "Chicago, IL" in the remarks, never "Lincoln Park, IL", and
# 15,000 of them is a tenth of the file for no benefit.
SUBDIVISION_CODES = frozenset({"PPLX"})

EXCLUDED_CODES = HISTORICAL_CODES | SUBDIVISION_CODES

STATE_CODES = frozenset(
    """AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN
    MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV
    WI WY""".split()
)


class Command(BaseCommand):
    help = "Rebuild the US place gazetteer from a GeoNames dump."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            required=True,
            type=Path,
            help="Path to the GeoNames US.txt export.",
        )
        parser.add_argument(
            "--output",
            type=Path,
            default=None,
            help="Where to write the CSV. Defaults to settings.PLACES_CSV.",
        )
        parser.add_argument(
            "--min-population",
            type=int,
            default=DEFAULT_MIN_POPULATION,
            help="Skip places below this population. 0 keeps every record.",
        )

    def handle(self, *args, **options):
        source: Path = options["source"]
        output: Path = options["output"] or Path(settings.PLACES_CSV)
        min_population: int = options["min_population"]

        if not source.exists():
            raise CommandError(
                f"{source} does not exist. Download it with:\n"
                "  curl -O https://download.geonames.org/export/dump/US.zip && unzip US.zip"
            )

        kept: list[tuple[str, str, str, str, int]] = []
        read = 0
        skipped_class = 0
        skipped_state = 0
        skipped_population = 0

        with source.open(encoding="utf-8", newline="") as handle:
            for line in handle:
                read += 1
                row = line.rstrip("\n").split("\t")
                if len(row) <= COL_POPULATION:
                    continue

                if row[COL_FEATURE_CLASS] != POPULATED_CLASS:
                    skipped_class += 1
                    continue
                if row[COL_FEATURE_CODE] in EXCLUDED_CODES:
                    skipped_class += 1
                    continue

                state = row[COL_STATE].strip().upper()
                if state not in STATE_CODES:
                    skipped_state += 1
                    continue

                population = int(row[COL_POPULATION] or 0)
                if population < min_population:
                    skipped_population += 1
                    continue

                name = row[COL_NAME].strip()
                if not name:
                    continue

                kept.append(
                    (name, state, row[COL_LATITUDE], row[COL_LONGITUDE], population)
                )

        kept.sort(key=lambda place: (place[0].lower(), place[1]))

        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["name", "state", "latitude", "longitude", "population"])
            writer.writerows(kept)

        self.stdout.write(
            f"read                          {read:>8}\n"
            f"  not a populated place       {skipped_class:>8}\n"
            f"  outside the 50 states + DC  {skipped_state:>8}\n"
            f"  below population {min_population:<10} {skipped_population:>8}\n"
            f"written                       {len(kept):>8}  -> {output}"
        )
