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

### Query latest stored athlete_day (for automations)
```bash
PYTHONPATH=. python3 scripts/get_latest_athlete_day.py
```

### Build Gold daily payload (merge policy + conflict handling)
```bash
PYTHONPATH=. python3 scripts/build_daily_gold.py --write --log-conflicts
```

### Inspect merge conflicts
```bash
PYTHONPATH=. python3 scripts/show_conflicts.py --limit 10
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
- Silver index: `backend/data/silver/index.json`

Silver writes are deterministic overwrite-by-day (no append/merge drift).

## Schemas
- Human-readable contracts: `backend/docs/SCHEMAS.md`
- Machine schema files: `backend/schemas/*.schema.json`

## Validation
```bash
PYTHONPATH=. python3 scripts/validate_silver.py
```

## Query layer
```bash
# Latest day consumer contract
PYTHONPATH=. python3 scripts/query_daily.py

# Specific day
PYTHONPATH=. python3 scripts/query_daily.py --day 2026-03-11

# Date range
PYTHONPATH=. python3 scripts/query_range.py --oldest 2026-03-10 --newest 2026-03-11
```

## Lightweight tests
```bash
cd backend
PYTHONPATH=. python3 -m unittest tests/test_query.py -v
```

## End-to-end smoke check
```bash
cd backend
PYTHONPATH=. python3 scripts/smoke_e2e.py
```

## PWA alpha shell payload
```bash
cd backend
PYTHONPATH=. python3 scripts/pwa_payload.py --write
```

Contract doc: `backend/docs/ALPHA_UI_CONTRACT.md`
Workout review contract: `backend/docs/WORKOUT_REVIEW_CONTRACT.md` (includes LLM-plan support + tiered matching/confidence)

## Alpha API + shell routes (Day 15/16)
```bash
cd backend
./scripts/run_alpha.sh
```

Default endpoints:
- `GET /api/health`
- `GET /api/alpha/routes`
- `GET /api/alpha/shell/today`
- `GET /api/alpha/shell/YYYY-MM-DD`
- `GET /api/alpha/workout/latest?day=YYYY-MM-DD`
- `GET /api/alpha/planner/modalities`
- `GET /api/alpha/planner/recommendation?sport=cycling&focusSport=cycling&feedbackDay=YYYY-MM-DD&athleteFeedback=easy|ok|hard&coachMode=true`
- `GET /api/alpha/planner/horizon?sport=cycling&focusSport=cycling`

Auth:
- set `PEAKFLOW_ALPHA_TOKEN` to require `Authorization: Bearer <token>`
- token can be entered in the alpha shell auth bar and is stored in localStorage

API smoke test:
```bash
cd backend
./scripts/smoke_api.py
# token mode
./scripts/smoke_api.py --token "your-alpha-token"
```

Frontend route skeleton (served by same process):
- `/` (Morning Brief)
- `#/recovery`
- `#/chat`
- `#/workout` (latest workout review)
- `#/plan` (daily activity selection + modality-specific recommendation)
