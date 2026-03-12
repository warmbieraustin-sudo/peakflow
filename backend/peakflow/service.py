from __future__ import annotations

from datetime import date
from typing import Any, Dict

from .intervals import IntervalsClient, build_athlete_day, normalize_activity, normalize_wellness


def get_daily_metrics(day: str | None = None, freshness_minutes: int = 180) -> Dict[str, Any]:
    """Single integration entrypoint for automation consumers.

    Returns a canonical payload with:
      - athlete_day (silver)
      - activities (silver/day slice)
      - readiness (freshness gate summary)
    """
    target_day = day or date.today().isoformat()
    client = IntervalsClient.from_env()

    wellness_rows = [normalize_wellness(r) for r in client.wellness(target_day, target_day)]
    activity_rows = [normalize_activity(r) for r in client.activities(target_day, target_day)]

    wellness = wellness_rows[-1] if wellness_rows else None
    athlete_day = build_athlete_day(
        target_day,
        wellness_row=wellness,
        activities=activity_rows,
        max_age_minutes=freshness_minutes,
    )

    activities = [a for a in activity_rows if (a.get("start_date_local") or "").startswith(target_day)]

    return {
        "date": target_day,
        "source": "intervals.icu",
        "athlete_day": athlete_day,
        "activities": activities,
        "readiness": {
            "recovery_fresh": athlete_day["freshness"]["is_fresh"],
            "reason": athlete_day["freshness"]["reason"],
            "age_minutes": athlete_day["freshness"]["age_minutes"],
            "max_age_minutes": athlete_day["freshness"]["max_age_minutes"],
        },
    }
