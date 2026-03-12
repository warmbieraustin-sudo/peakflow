# Workout Review Contract (Day 17/18/19)

Priority order for review generation:
1. **TrainingPeaks** = prescription (planned workout + structure)
2. **Intervals.icu** = execution (actual activity metrics)
3. **Garmin** = fallback (when execution missing)

## Supports both plan sources
- **trainingpeaks** structured plans
- **llm** generated plans (must be normalized to interval schema)

LLM/TP interval schema:
```json
{
  "label": "10m threshold",
  "type": "work",
  "duration_sec": 600,
  "target_type": "power_watts|power_pct_ftp|hr_bpm|rpe",
  "target_low": 85,
  "target_high": 95
}
```

## Payload shape

```json
{
  "date": "YYYY-MM-DD",
  "prescription": {
    "source": "trainingpeaks",
    "status": "ok|empty|unavailable",
    "workout_title": "...",
    "planned_tss": 85,
    "planned_duration_sec": 3600,
    "intervals": [
      {
        "index": 0,
        "type": "work",
        "duration_sec": 600,
        "target_type": "power_pct_ftp",
        "target_low": 85,
        "target_high": 95,
        "label": "10m threshold"
      }
    ]
  },
  "execution": {
    "source": "intervals.icu",
    "status": "ok|empty",
    "activity": {
      "id": "i...",
      "weighted_avg_watts": 205,
      "avg_hr": 148,
      "training_load": 72,
      "decoupling": 2.4,
      "calories": 790
    }
  },
  "analysis": {
    "prescription_available": true,
    "execution_available": true,
    "matching_tier": "power_hr|hr_only|duration_only|none",
    "interval_matching": "matched|partial|missed|not_available",
    "score": 84.5,
    "confidence": "high|medium|low",
    "reason_codes": ["SESSION_LEVEL_POWER_MATCH"],
    "intervals": [
      {
        "label": "10m threshold",
        "target_type": "power_pct_ftp",
        "target_low": 85,
        "target_high": 95,
        "executed": 88.0,
        "delta": -2.0,
        "hit": true
      }
    ]
  },
  "fallbacks": {
    "garmin_fallback_required": false
  }
}
```

## Matching tiers
- `power_hr`: best quality (power+HR signals)
- `hr_only`: no reliable power, HR/intensity fallback
- `duration_only`: non-data-rich user baseline
- `none`: no execution signals

## Access
- Script: `scripts/latest_workout_review.py --day YYYY-MM-DD`
- Alpha API: `GET /api/alpha/workout/latest?day=YYYY-MM-DD`
