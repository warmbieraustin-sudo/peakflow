# PeakFlow Backend

## Intervals.icu integration (Sprint Days 2-4)

Current capabilities:
- fetch daily wellness (weight, resting HR, HRV, sleep, CTL/ATL)
- fetch activities (NP, training load, decoupling, calories, kJ)
- persist **Bronze** snapshots (raw source payloads)
- persist **Silver** normalized records (`athlete_day`, `activities_by_day`)
- compute freshness gate for morning-report readiness
- expose a single automation entrypoint: `get_daily_metrics()`

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

### Single function/automation entrypoint
```bash
PYTHONPATH=. python3 scripts/get_daily_metrics.py --compact --fresh-minutes 180
```

### First consumer: morning readiness gate
```bash
PYTHONPATH=. python3 scripts/check_recovery_freshness.py --fresh-minutes 180
# exit 0 => ready, exit 1 => not ready
```

## Output locations
- Bronze snapshots: `backend/data/snapshots/`
- Silver athlete_day: `backend/data/silver/athlete_day/YYYY-MM-DD.json`
- Silver activities: `backend/data/silver/activities/YYYY-MM-DD.json`

## Schemas
See `backend/docs/SCHEMAS.md`.
