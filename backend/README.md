# PeakFlow Backend

## Intervals.icu starter integration (Sprint Days 1-2)

This module fetches:
- daily wellness (weight, resting HR, HRV, sleep, CTL/ATL)
- recent activities (NP, training load, decoupling, calories)

## Setup

```bash
cd backend
cp .env.example .env
# fill INTERVALS_ICU_API_KEY + INTERVALS_ICU_ATHLETE_ID
```

## Run

```bash
cd backend
PYTHONPATH=. python3 scripts/intervals_snapshot.py --days 1 --write
```

Or pull a custom range:

```bash
PYTHONPATH=. python3 scripts/intervals_snapshot.py --oldest 2026-03-01 --newest 2026-03-11 --write
```

Snapshot files are written to `backend/data/snapshots/`.
