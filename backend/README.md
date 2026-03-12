# PeakFlow Backend

## Intervals.icu integration (Sprint Days 2-4)

Current capabilities:
- fetch daily wellness (weight, resting HR, HRV, sleep, CTL/ATL)
- fetch activities (NP, training load, decoupling, calories, kJ)
- persist **Bronze** snapshots (raw source payloads)
- persist **Silver** normalized records (`athlete_day`, `activities_by_day`)
- compute freshness gate for morning-report readiness

## Setup

```bash
cd backend
cp .env.example .env
# fill INTERVALS_ICU_API_KEY + INTERVALS_ICU_ATHLETE_ID
```

## Run

### Bronze only
```bash
cd backend
PYTHONPATH=. python3 scripts/intervals_snapshot.py --days 1 --write
```

### Bronze + Silver + freshness
```bash
PYTHONPATH=. python3 scripts/intervals_snapshot.py --days 1 --write --silver --fresh-minutes 180
```

### Custom range
```bash
PYTHONPATH=. python3 scripts/intervals_snapshot.py \
  --oldest 2026-03-01 --newest 2026-03-11 \
  --write --silver --fresh-minutes 180
```

## Output locations
- Bronze snapshots: `backend/data/snapshots/`
- Silver athlete_day: `backend/data/silver/athlete_day/YYYY-MM-DD.json`
- Silver activities: `backend/data/silver/activities/YYYY-MM-DD.json`

## Schemas
See `backend/docs/SCHEMAS.md`.
