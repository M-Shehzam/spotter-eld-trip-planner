# Spotter AI — ELD Trip Planner: Build Plan

Assessment: build a Django + React app that takes trip details and returns route
instructions plus filled-in driver daily log sheets.

| | |
|---|---|
| Brief received | 21 Aug 2026 |
| Deadline | 25 Aug 2026 (4 days) |
| Budget | 16 work hours |
| Deliverables | GitHub repo link, hosted URL, 3–5 min Loom |
| Repo | `spotter-eld-trip-planner` (public monorepo) |
| Local path | `/Users/shehzam/Downloads/Code/spotter-eld-trip-planner` |

---

## 1. What the brief asks for

**Inputs**

- Current location
- Pickup location
- Dropoff location
- Current cycle used (hrs)

**Outputs**

- Map showing the route with stops and rests, using a free map API
- Daily log sheets, drawn and filled out; several sheets for longer trips

**Stated assumptions**

- Property-carrying driver, 70 hrs / 8 days, no adverse driving conditions
- Fuel at least once every 1,000 miles
- 1 hour for pickup and 1 hour for dropoff

**Grading**

- The hosted version gets tested for accuracy
- UI and UX are judged directly, and good design offsets some inaccuracy

---

## 2. Architecture

```
┌──────────────────────────┐        ┌────────────────────────────────┐
│  React 18 + Vite + MUI   │        │  Django 5 + DRF                │
│  Vercel                  │        │  Render (gunicorn + whitenoise)│
│                          │        │                                │
│  TripForm                │ POST   │  /api/v1/trips/                │
│  RouteMap (react-leaflet)│ ─────► │  /api/v1/trips/{id}/           │
│  TripSummary             │ ◄───── │  /api/v1/places/suggest/       │
│  StopsTimeline           │  JSON  │  /api/v1/health/               │
│  LogSheet (SVG)          │        │                                │
└──────────────────────────┘        └───────────┬────────────────────┘
                                                │
                          ┌─────────────────────┼─────────────────────┐
                          ▼                     ▼                     ▼
                 ┌────────────────┐   ┌──────────────────┐  ┌────────────────┐
                 │ PlaceIndex     │   │ RoutingProvider  │  │ HOS engine     │
                 │ us_places.csv  │   │ OSRM (1 call)    │  │ pure Python,   │
                 │ 27k US places  │   │ polyline decode  │  │ no I/O         │
                 │ offline        │   │ + fallback       │  │ FMCSA 395      │
                 └────────────────┘   └──────────────────┘  └───────┬────────┘
                                                                     ▼
                                                            ┌────────────────┐
                                                            │ LogBuilder     │
                                                            │ slice at       │
                                                            │ midnight,      │
                                                            │ totals, recap  │
                                                            └────────────────┘
```

One outbound HTTP call per trip (OSRM). Everything else runs against data
committed in the repo, so a cold clone works with no API keys.

### Reused from `spotter-fuel-route-api`

Ported with the commits noting where they came from:

| Module | What it gives us |
|---|---|
| `routing/providers.py` | OSRM client, retry, fallback provider, `RouteResult` |
| `routing/polyline.py` | Encoded polyline decoder |
| `routing/resolver.py` | Free-text place → coordinates, `PlaceIndex` |
| `routing/geo.py` | Haversine, bearing, bbox helpers |
| `data/us_places.csv` | 27,093 US places with population |
| `config/settings.py` | Env handling, cache config, logging |

New in this project: prefix search and nearest-place lookup on `PlaceIndex`,
the HOS engine, the log builder, and the entire frontend.

---

## 3. Domain model

### Request

```json
{
  "current_location": "Chicago, IL",
  "pickup_location": "St. Louis, MO",
  "dropoff_location": "Dallas, TX",
  "current_cycle_used_hours": 14.5,
  "start_datetime": "2026-08-24T06:00:00",   // optional, defaults to now
  "driver_name": "M. Shehzam",               // optional, prints on the sheet
  "carrier_name": "Spotter Logistics",       // optional
  "truck_number": "1842"                     // optional
}
```

Only the first four are required. The rest exist because a real log sheet has
those fields and leaving them blank looks unfinished.

### Response

```jsonc
{
  "id": "uuid",
  "inputs": { ... },
  "route": {
    "geometry": [[lat, lon], ...],
    "bbox": [west, south, east, north],
    "distance_miles": 1043.2,
    "drive_hours": 18.4,
    "legs": [
      {"from": "Chicago, IL", "to": "St. Louis, MO", "distance_miles": 297.1, "drive_hours": 5.2},
      {"from": "St. Louis, MO", "to": "Dallas, TX",  "distance_miles": 746.1, "drive_hours": 13.2}
    ]
  },
  "stops": [
    {"seq": 1, "type": "pickup", "label": "St. Louis, MO", "lat": .., "lon": ..,
     "mile_marker": 297.1, "arrive": "ISO", "depart": "ISO", "duration_hours": 1.0}
  ],
  "segments": [
    {"start": "ISO", "end": "ISO", "status": "driving",
     "label": "Chicago, IL → St. Louis, MO", "miles": 297.1}
  ],
  "logs": [
    {
      "sheet_number": 1, "of": 3, "date": "2026-08-24",
      "from_label": "Chicago, IL", "to_label": "Effingham, IL",
      "total_miles_driving": 512, "total_mileage": 512,
      "grid": [{"status": "off_duty", "start_hour": 0.0, "end_hour": 6.0}, ...],
      "remarks": [{"hour": 6.0, "text": "Chicago, IL — begin trip"}],
      "totals": {"off_duty": 8.0, "sleeper": 0.0, "driving": 11.0, "on_duty": 5.0},
      "recap": {"on_duty_today": 16.0, "on_duty_last_7": 30.5,
                "available_tomorrow": 39.5, "on_duty_last_8": 30.5}
    }
  ],
  "summary": {
    "days": 3, "total_drive_hours": 18.4, "total_on_duty_hours": 22.4,
    "total_off_duty_hours": 31.0, "arrival": "ISO", "elapsed_hours": 53.4,
    "fuel_stops": 1, "rest_breaks": 2, "restarts": 0,
    "cycle_hours_at_finish": 36.9, "violations": []
  },
  "meta": {"provider": "osrm", "api_calls": 1, "computed_ms": 412}
}
```

`GET /api/v1/trips/{id}/` returns the same payload, which makes every plan a
shareable link.

### Storage

One `Trip` model: the input fields, the computed plan as `JSONField`, and
`created_at`. Planning is deterministic, so a repeat of the same inputs is served
from cache keyed on a hash of the inputs.

---

## 4. Routing

1. Resolve the three place strings against `PlaceIndex` — no network call.
2. One OSRM request: `current → pickup → dropoff`, `overview=full`,
   `geometries=polyline`. Returns the full geometry and per-leg distance and
   duration.
3. Build a distance profile: for each geometry vertex, cumulative miles from the
   origin. Given any mile marker, we can interpolate the coordinate. That is how
   fuel stops and rest stops get placed on the map without extra API calls.
4. Driving time = OSRM duration × `TRUCK_SPEED_FACTOR` (default **1.15**). OSRM's
   demo profile is a car; the factor brings a typical interstate run to roughly
   55–58 mph average, which is what a planner would use for a Class 8 truck. The
   value is an env var and the README says why it exists.

---

## 5. HOS engine — the part that gets graded

Pure Python, no Django imports, no I/O. A forward simulation over a timeline.

### State

| Field | Resets on |
|---|---|
| `clock` | — |
| `drive_since_reset` (11-hr limit) | 10 consecutive hrs off duty or sleeper |
| `window_start` (14-hr window) | 10 consecutive hrs off duty or sleeper |
| `drive_since_break` (8-hr limit) | any ≥30 min in a non-driving status |
| `cycle_used` (70 hrs / 8 days) | 34 consecutive hrs off duty |
| `miles_since_fuel` | fuel stop |

`cycle_used` starts at the driver's `current_cycle_used_hours`.

### Rules implemented (49 CFR 395.3)

1. **11-hour driving limit** — no more than 11 hrs driving after 10 consecutive
   hrs off duty.
2. **14-hour window** — no driving beyond the 14th hour after coming on duty.
   Off-duty time inside the window does not extend it.
3. **30-minute break** — required after 8 cumulative hrs of driving. Satisfied by
   30 consecutive minutes in *any* non-driving status, per the 2020 final rule.
   This matters: the 1-hour pickup is on-duty-not-driving, so it clears the break
   requirement on its own. Getting that right is the detail that separates a real
   implementation from a guess.
4. **70-hour / 8-day cycle** — no driving once 70 on-duty hours accumulate.
5. **34-hour restart** — 34 consecutive hrs off duty zeroes the cycle. Only
   inserted when the cycle is the binding constraint, because it costs a day and
   a half.

Documented as out of scope in the README: the sleeper-berth split (7/3 and 8/2),
the 16-hour short-haul exception, and the adverse-conditions extension. The brief
rules out adverse conditions, and the splits do not change the output for a
single continuous dispatch.

### Loop

```
for activity in [DRIVE(leg0), ON_DUTY(1h, pickup), DRIVE(leg1), ON_DUTY(1h, dropoff)]:

    if activity is DRIVE:
        remaining_hours = leg.drive_hours
        while remaining_hours > 0:

            budget = min(11 - drive_since_reset,
                         14 - hours_since(window_start),
                         8  - drive_since_break,
                         70 - cycle_used)

            if budget <= 0:
                insert_required_rest()      # see below
                continue

            miles_to_fuel = 1000 - miles_since_fuel
            hours_to_fuel = miles_to_fuel / average_speed
            chunk = min(remaining_hours, budget, hours_to_fuel)

            emit DRIVING for chunk
            advance all counters

            if miles_since_fuel >= 1000:
                emit ON_DUTY 0.5h "Fuel — {nearest place}"

    if activity is ON_DUTY:
        if 14 - hours_since(window_start) < duration or 70 - cycle_used < duration:
            insert_required_rest()
        emit ON_DUTY for duration
```

`insert_required_rest()` picks the cheapest fix that unblocks the binding limit:

| Binding limit | Inserted |
|---|---|
| cycle exhausted (70 hrs) | 34-hr restart, off duty |
| 8 hrs driving since last break | 30-min break, off duty |
| 11-hr drive limit or 14-hr window | 10-hr rest, sleeper berth |

The 10-hour rest is drawn on the **sleeper berth** row and short breaks on the
**off duty** row, which is how an over-the-road driver actually logs them.

Every emitted segment carries the mile marker, so its coordinate and nearest
place name come from the distance profile and the gazetteer.

### Tests

One test class per rule, each with a hand-computed expectation:

- short trip, no rest needed
- trip that hits the 11-hour limit exactly
- trip where the 14-hour window binds before the 11-hour limit
- pickup satisfying the 30-minute break
- driver starting at 68/70 cycle hours, forcing a 34-hour restart
- 2,400-mile trip taking exactly 3 fuel stops
- property: on-duty + off-duty + driving = elapsed, on every generated plan
- property: no plan ever exceeds 11 driving in a window, or 14 elapsed on duty

---

## 6. Log sheet builder

Takes the flat segment list and produces one sheet per calendar day in the home
terminal timezone.

- Split any segment crossing midnight into two.
- Convert each segment to `{status, start_hour, end_hour}` with hours as floats
  0–24, which is exactly what the SVG grid needs.
- Per-status day totals, rounded to the nearest quarter hour the way a paper log
  is filled in, with the rounding reconciled so the four totals sum to 24.
- Driving miles for the day, from the mile markers.
- Remarks: every duty status change with its time and nearest city.
- Recap boxes: on-duty today, on-duty in the last 7 days, hours available
  tomorrow (70 minus the last 7 days including today), on-duty in the last 8 days.

---

## 7. Frontend

React 18 + Vite + TypeScript + MUI v5. Leaflet through `react-leaflet`, with
CARTO Voyager tiles — free, no key, and better looking than raw OSM.

| Component | Job |
|---|---|
| `TripForm` | Three MUI `Autocomplete` fields backed by `/places/suggest/`, a cycle-hours slider with numeric entry, optional start time and driver details behind a collapse |
| `TripSummary` | Stat cards: distance, driving time, days, arrival, HOS status |
| `RouteMap` | Polyline, numbered stop markers colour-coded by type, popups, fit-to-bounds |
| `StopsTimeline` | Vertical MUI timeline of every stop and rest with times |
| `LogSheetGrid` | The SVG replica — one per day |
| `LogSheetTabs` | Day-by-day navigation, download PNG, print all |

Design intent: dark-first theme with a single accent, generous spacing, the map
and the summary above the fold, the log sheets below. Skeletons while the plan
computes, and a distinct message for a cold backend. Responsive down to a phone
with the map stacking above the summary.

### SVG log sheet

Hand-built to match `blank-paper-log.png`:

- Header: month/day/year, from, to, carrier, terminal address, truck number
- Total miles driving today and total mileage boxes
- 24-hour grid, 4 duty rows, quarter-hour ticks, midnight-to-midnight
- The stepped duty line drawn across the grid with vertical connectors at each
  status change
- Right-hand per-row total hours
- Remarks with time-positioned tick marks and rotated labels
- The 70-hr/8-day recap boxes filled in

Scales cleanly, prints, and exports to PNG through a canvas serialisation.

---

## 8. Phases

Each phase ends in a commit that passes its tests.

| # | Phase | Output | Est |
|---|---|---|---|
| P0 | Repo scaffold | Monorepo, Django project, Vite app, CI-ready, health endpoint green | 1.0h |
| P1 | Places | `PlaceIndex` ported plus prefix search and nearest-place; `/places/suggest/` | 0.75h |
| P2 | Routing | OSRM provider ported, 3-waypoint request, distance profile, mile→coord | 1.0h |
| P3 | HOS engine | The simulator and its rule tests | 3.0h |
| P4 | Log builder | Day slicing, totals, recap, remarks | 1.25h |
| P5 | API | DRF serializers, `POST/GET /trips/`, caching, error contract, tests | 1.25h |
| P6 | Frontend shell | Theme, layout, form with autocomplete, API client, loading states | 1.5h |
| P7 | Map & summary | Leaflet route, stop markers, stat cards, timeline | 1.5h |
| P8 | Log sheet SVG | The grid, the duty line, remarks, recap, export | 2.5h |
| P9 | Polish | Responsive pass, empty and error states, print CSS, accessibility | 1.0h |
| P10 | Deploy | Render backend, Vercel frontend, CORS, keep-warm, smoke test | 1.0h |
| P11 | Docs & Loom | README, screenshots, script, record | 1.25h |
| | | **Total** | **17.0h** |

Slightly over the 16-hour budget on paper. P9 is the compressible one.

### Cut list, in the order things get dropped

1. PNG export of the log sheet (print still works)
2. The stops timeline (the map popups already carry the information)
3. Optional driver and carrier fields (hardcode sensible defaults)

Never cut: HOS correctness, the log sheet drawing, the map, the deploy.

---

## 9. Risks

| Risk | Mitigation |
|---|---|
| OSRM demo server down during review | Fallback provider env var, plus a cached demo trip that renders with no network |
| Render free tier cold start (~50s) | Keep-warm ping every 10 min, and the UI says "waking the server" instead of hanging |
| Gazetteer misses a small town | Falls back to the nearest match and accepts raw `lat,lon`; the error message says so |
| HOS edge case wrong | Property-based invariant tests catch limit violations that unit tests miss |
| Time overrun | Phases are independently shippable; the cut list is decided in advance |

---

## 10. Deliverables and where they live

```
/Users/shehzam/Downloads/Code/spotter-eld-trip-planner/
├── PLAN.md                  ← this file
├── README.md                ← what a reviewer reads first
├── backend/                 ← Django, deployed to Render
├── frontend/                ← React, deployed to Vercel
└── docs/
    ├── LOOM_SCRIPT.md       ← 5-minute script with on-screen cues
    ├── SUBMISSION.md        ← the three links, ready to paste
    └── screenshots/
```
