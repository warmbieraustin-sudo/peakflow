# PeakFlow Adapter Onboarding Checklist

Use this when adding a new source adapter (e.g., Strava, Garmin, WHOOP).

## 1) Source setup
- [ ] Confirm auth flow and token refresh strategy
- [ ] Define required scopes/permissions
- [ ] Add env keys to `backend/.env.example`

## 2) Adapter implementation
- [ ] Create adapter module under `peakflow/adapters/`
- [ ] Implement raw fetch for wellness + activities (or equivalent)
- [ ] Normalize source payloads to canonical Silver schema

## 3) Merge policy
- [ ] Add source to canonical name map
- [ ] Update field-level priority map in `peakflow/merge.py`
- [ ] Define conflict handling for known disagreeing fields

## 4) Validation
- [ ] Run `scripts/intervals_snapshot.py --silver` equivalent for new source (or merged pipeline)
- [ ] Run `scripts/validate_silver.py`
- [ ] Run `scripts/build_daily_gold.py --write --log-conflicts`
- [ ] Check `data/silver/conflicts/*.jsonl` for expected/acceptable conflicts

## 5) Consumer contract safety
- [ ] Verify `scripts/query_daily.py` still returns stable contract
- [ ] Run `scripts/smoke_e2e.py`
- [ ] Confirm one production consumer path renders expected values

## 6) Operational readiness
- [ ] Add failure alerting for adapter fetch errors
- [ ] Add runbook note for auth expiry/re-auth
- [ ] Document rollout plan (alpha only -> staged beta)
