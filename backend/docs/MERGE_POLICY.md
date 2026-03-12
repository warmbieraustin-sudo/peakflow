# PeakFlow Day 10 Merge Policy (Gold Layer)

## Goal
Merge one or more Silver `athlete_day` records from different sources into a single Gold payload with:
- deterministic source selection
- provenance per merged field
- conflict capture for auditability

## Current state
- Active source in pipeline: `intervals` (from `intervals.icu`)
- Other sources are scaffolded for future onboarding (`garmin`, `strava`, `whoop`)

## Policy model

### 1) Field-level source priority
Examples:
- `recovery.weight_kg`: `garmin > intervals > strava`
- `recovery.hrv`: `garmin > whoop > intervals`
- `load.ctl`: `intervals > strava > garmin`

### 2) Deterministic pick
For each field:
- collect non-null candidates from all sources
- choose the highest-priority source for that field
- persist chosen source in `provenance`

### 3) Conflict logging
If two or more distinct non-null values exist for the same field:
- emit a conflict object with chosen value, alternatives, and policy path
- append to `data/silver/conflicts/YYYY-MM-DD.jsonl` (optional flag)

## Output
`data/gold/daily/YYYY-MM-DD.json` contains:
- `merged` (final selected values)
- `freshness` (readiness summary)
- `provenance` (field -> chosen source)
- `conflicts` + `conflict_count`

## Why this matters
As additional providers come online, this prevents silent data drift and keeps coaching logic deterministic and debuggable.
