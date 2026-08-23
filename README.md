# Spotter ELD Trip Planner

Enter a trip, get a route and a set of filled-in driver daily log sheets that
respect the federal hours-of-service rules.

Built for the Spotter AI full-stack assessment. Django + DRF on the back,
React + MUI on the front.

**Live app** · **API** · **Loom walkthrough** — links in `docs/SUBMISSION.md`

---

## What it does

Give it four things:

- current location
- pickup location
- dropoff location
- hours already used in the current 70-hour cycle

It returns a drivable route with every required stop placed on it, and one
drawn log sheet per day of the trip.

## Status

Under construction. See `PLAN.md` for the build plan and phase breakdown.

## Running locally

```bash
# Backend
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
cp backend/.env.example backend/.env
cd backend && ../.venv/bin/python manage.py migrate && ../.venv/bin/python manage.py runserver

# Frontend, in a second shell
cd frontend
npm install
cp .env.example .env
npm run dev
```

Backend on `http://127.0.0.1:8000`, frontend on `http://localhost:5173`.
No API keys are needed.

## Tests

```bash
cd backend && ../.venv/bin/python -m pytest
```
