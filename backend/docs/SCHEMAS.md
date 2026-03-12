# PeakFlow Canonical Schemas (Silver Layer)

## `athlete_day` (one file per date)

Path: `backend/data/silver/athlete_day/YYYY-MM-DD.json`

```json
{
  "date": "2026-03-11",
  "source": "intervals.icu",
  "recovery": {
    "weight_kg": 66.93,
    "resting_hr": 44,
    "hrv": 95.0,
    "sleep_seconds": 30720,
    "sleep_score": 86.0
  },
  "load": {
    "ctl": 54.5,
    "atl": 67.2,
    "ramp_rate": 3.34,
    "daily_training_load": 55.0
  },
  "activity_summary": {
    "count": 1,
    "total_calories": 944,
    "total_kj": 988.65,
    "avg_np": 138.0
  },
  "freshness": {
    "is_fresh": true,
    "reason": "ok",
    "updated": "2026-03-12T01:17:40.599+00:00",
    "age_minutes": 42.7,
    "max_age_minutes": 180
  },
  "raw_refs": {
    "wellness_updated": "2026-03-12T01:17:40.599+00:00",
    "activity_ids": ["i131367053"]
  }
}
```

## `activities_by_day` (one file per date)

Path: `backend/data/silver/activities/YYYY-MM-DD.json`

```json
[
  {
    "id": "i131367053",
    "name": "Zwift",
    "type": "VirtualRide",
    "start_date_local": "2026-03-11T15:54:29",
    "moving_time_sec": 7259,
    "distance_m": 61229.31,
    "avg_hr": 115,
    "max_hr": 128,
    "weighted_avg_watts": 138,
    "training_load": 55,
    "intensity": 52.07547,
    "decoupling": 1.1231862,
    "kj": 988.65,
    "calories": 944,
    "source_updated": null
  }
]
```

## Notes
- **Bronze** = raw source records (`backend/data/snapshots/*`).
- **Silver** = normalized canonical records used by automations.
- **Gold** (next) = decision features + coaching outputs.

## Freshness contract (morning report)
- `athlete_day.freshness.is_fresh` is the one-flag gate.
- Threshold is set by `--fresh-minutes` in `intervals_snapshot.py`.
- Default currently: `180` minutes.
