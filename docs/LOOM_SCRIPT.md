# Loom script

Target 4:00. The brief allows 3 to 5 minutes and says the hosted version is
tested for accuracy, so the demo runs against the live URL, not localhost.

## Before recording

- [ ] Open the hosted app and plan one trip, so Render is awake
- [ ] Close every other tab. Two windows only: the app and the editor
- [ ] Editor at 16pt or larger. Code has to be readable at 720p
- [ ] Open these files as tabs, in this order:
      `hos.py`, `logsheet.py`, `LogSheetSvg.tsx`
- [ ] In `hos.py`, scroll to `_drive_budget`
- [ ] Have the trip ready to type: `Newark, NJ` / `Chicago, IL` /
      `Los Angeles, CA`, cycle `20`
- [ ] Microphone check. One take, no editing

Numbers to have in your head, because you will be asked:

- 2,798 miles, 7 days, 7 log sheets
- 297 backend tests, 15 frontend, 28 Playwright checks
- 385 ms to load 31,000 places, 37 MB held

---

## 0:00 - 0:25 | What it is

**SHOW:** the hosted app, empty state, nothing typed yet.

> This is a trip planner for property-carrying truck drivers. You give it
> where the driver is, where the load gets picked up and dropped off, and how
> many hours of their seventy-hour cycle are already spent. It gives back a
> route with every stop the federal rules require, and a filled-in daily log
> sheet for each day.
>
> Django and REST framework on the back, React on the front. Nothing here
> needs an API key.

## 0:25 - 1:25 | Plan a trip

**SHOW:** type into the three fields. Let the autocomplete list open on the
first one and pause half a second so it registers on camera.

> Newark, New Jersey. Pickup in Chicago. Dropoff in Los Angeles. Twenty hours
> already used.
>
> The autocomplete is not calling a geocoding service. Thirty-one thousand US
> places ship inside the app and resolve in memory, which is also why there is
> no key to leak.

**SHOW:** click Plan trip. Let the route draw.

> Two thousand eight hundred miles, seven days.

**SHOW:** point at the stat tiles, then the map markers.

> The route comes from one OSRM call. Every marker on it is a stop the rules
> forced: fuel at least every thousand miles, ten hours in the sleeper when
> the eleven-hour driving limit runs out, a thirty-four hour restart when the
> cycle does.

**SHOW:** scroll to the compliance banner.

> And this line matters more than it looks. The backend re-checks every
> finished plan against the regulation with a second, independent
> implementation, and ships that verdict in the response. I will come back to
> it.

## 1:25 - 2:20 | The log sheets

**SHOW:** scroll to the log sheets. Let one full sheet fill the screen.

> This is the deliverable the brief actually names. It is a redraw of the
> paper form, drawn as SVG and filled from the plan.

**SHOW:** trace with the cursor as you speak: hour strip, the four rows, the
duty line, the totals column.

> Twenty-four hours across, quarter-hour ticks, the four duty rows in the
> order the form prints them. The duty line is one path, so the vertical at
> each status change is the same stroke as the run either side of it, the way
> a driver draws it.
>
> Totals on the right, and they have to add to twenty-four. That check is in
> the test suite.

**SHOW:** click through to day three.

> Longer trips need more sheets. This one needs seven.
>
> Day three shows thirteen hours of driving, which looks illegal and is not.
> The eleven-hour limit runs per shift, not per calendar day, and this day
> holds the end of one shift and the start of another with ten hours of
> sleeper between them.

**SHOW:** point at recap box C, empty.

> Box C is deliberately empty. It wants on-duty hours across the last seven
> days. The driver gives one cycle number with no day-by-day breakdown, so
> until the trip itself has run seven days there is nothing to put there but a
> guess, and a guess on a federal form is worse than a blank.

**SHOW:** click Download PNG, then Print all, and close the print dialog.

> Each sheet exports as a PNG, and printing puts every day on its own page.

## 2:20 - 3:20 | The code

**SHOW:** switch to the editor, `hos.py`, `_drive_budget` on screen.

> This is the core. Before every stretch of driving the planner asks how long
> this driver may keep going, and the answer is the smallest of four numbers:
> what is left of the eleven-hour driving limit, of the fourteen-hour duty
> window, of the eight hours before a break is due, and of the seventy-hour
> cycle.

**SHOW:** scroll to `_clear_the_way`.

> When the budget hits zero it picks the cheapest fix that actually unblocks
> the trip. Cycle exhausted means a thirty-four hour restart. Drive limit or
> window means ten hours off. Otherwise a thirty-minute break.

**SHOW:** scroll to `audit`.

> And here is the second implementation I mentioned. It re-walks the finished
> plan and checks the same four limits from scratch. If the planner has a bug,
> this catches it instead of agreeing with it.

**SHOW:** `logsheet.py`, the `_slice_into_days` function.

> One more thing worth showing. A trip does not respect midnight, so the plan
> gets cut at local midnight and the miles split proportionally across the
> boundary. That is what turns one drive into seven sheets.

## 3:20 - 3:50 | Why I trust it

**SHOW:** terminal, run `pytest -q` and let it finish, or have it already run.

> Two hundred and ninety-seven tests on the backend, covering each rule case
> by case. Fifteen on the frontend for the sheet geometry.

**SHOW:** the Playwright suite output, 28/28.

> And twenty-eight checks that drive the running app: every sheet accounting
> for twenty-four hours, sheet mileage matching route distance, print output,
> four screen widths, and an accessibility audit that comes back clean.
>
> Every real bug in this project was found by looking at the rendered page,
> not by a unit test. The suite exists because of that.

## 3:50 - 4:00 | Close

**SHOW:** back to the hosted app, whole page.

> Repo and hosted link are in the submission. Thanks for watching.

---

## If you overrun

Cut in this order:

1. `logsheet.py` and the midnight slicing, at 3:05
2. The PNG and print click, at 2:15
3. The 13-hour explanation on day three, at 2:00

Never cut: the drawn sheet, `_drive_budget`, or `audit`.
