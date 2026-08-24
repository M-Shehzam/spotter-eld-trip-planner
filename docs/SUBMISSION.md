# Submission

Three links go into the Teamtailor form on Ena's message.

| Field | Link |
| --- | --- |
| GitHub code | https://github.com/M-Shehzam/spotter-eld-trip-planner |
| Hosted version | https://TODO.vercel.app |
| Loom video | https://TODO.loom.com |

## Before submitting

- [ ] Open the hosted link in a private window and plan a trip end to end
- [ ] Confirm the log sheets draw and the tabs switch
- [ ] Confirm the Loom is public and plays without a login
- [ ] Confirm the repo is public
- [ ] Watch the Loom once at full length and check it runs 3 to 5 minutes

## What the brief asked for, and where it is

| Requirement | Where |
| --- | --- |
| Django and React | `backend/` Django 5.1 and DRF, `frontend/` React 19 |
| Four inputs | `frontend/src/components/TripForm.tsx` |
| Map with stops and rests, free API | `RouteMap.tsx`, OSRM and OpenStreetMap tiles |
| Log sheets drawn and filled | `frontend/src/components/logsheet/` |
| Multiple sheets on longer trips | `backend/apps/planner/logsheet.py` |
| 70 hours over 8 days | `backend/apps/planner/hos.py` |
| Fuel every 1,000 miles | `FUEL_INTERVAL_MILES` in `config/settings.py` |
| 1 hour for pickup and dropoff | `PICKUP_HOURS`, `DROPOFF_HOURS` |
