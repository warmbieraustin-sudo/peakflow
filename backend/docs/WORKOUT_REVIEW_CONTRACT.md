# Workout Review Contract (Day 17)

Priority order for review generation:
1. **TrainingPeaks** = prescription (planned workout + structure)
2. **Intervals.icu** = execution (actual activity metrics)
3. **Garmin** = fallback (when execution missing)

## Payload shape

```json
{
  "date": "YYYY-MM-DD",
  "prescription": {
    "source": "trainingpeaks",
    "status": "ok|empty|unavailable",
    "workout_title": "...",
    "intervals": [
      {
        "index": 0,
        "type": "work",
        "duration_sec": 600,
        "target_power_low": 240,
        "target_power_high": 260,
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
    "interval_matching": "pending|not_available"
  },
  "fallbacks": {
    "garmin_fallback_required": false,
    "tp_error": null
  }
}
```

## Access
- Script: `scripts/latest_workout_review.py --day YYYY-MM-DD`
- Alpha API: `GET /api/alpha/workout/latest?day=YYYY-MM-DD`
