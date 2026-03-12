# PeakFlow Alpha UI Contract (Day 14)

Goal: define the minimal, stable payloads needed to ship the first PWA shell screens.

## Source
Generated from `scripts/pwa_payload.py`, backed by Silver consumer contract.

## Screens

### 1) Morning Brief
Path: `screens.morning_brief`

Required fields:
- `headline.fresh`
- `headline.freshness_age_minutes`
- `quick_recovery.weight_kg`
- `quick_recovery.resting_hr`
- `quick_recovery.hrv`
- `quick_recovery.sleep_score`
- `quick_load.ctl`
- `quick_load.atl`
- `quick_load.daily_training_load`

### 2) Recovery + Load
Path: `screens.recovery_load`

Required fields:
- `recovery.*`
- `load.*`
- `activity_summary.*`

### 3) Chat Context
Path: `screens.chat_context`

Required fields:
- `date`
- `fresh`
- `recovery.*`
- `load.*`
- `activity_summary.*`
- `activity_count`

## Refresh behavior
- Morning report logic should treat freshness as the primary readiness signal.
- PWA can refresh this payload on app open and manual pull-to-refresh.

## Fallback behavior
If payload unavailable:
- Render stale-state banner
- Show cached last-good payload if available
- Offer retry action

## Command
```bash
cd backend
PYTHONPATH=. python3 scripts/pwa_payload.py --write
```
