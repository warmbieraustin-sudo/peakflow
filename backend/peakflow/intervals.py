from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, List
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import load_env, require_env


BASE_URL = "https://intervals.icu/api/v1"


@dataclass
class IntervalsClient:
    athlete_id: str
    api_key: str

    @classmethod
    def from_env(cls) -> "IntervalsClient":
        load_env()
        return cls(
            athlete_id=require_env("INTERVALS_ICU_ATHLETE_ID"),
            api_key=require_env("INTERVALS_ICU_API_KEY"),
        )

    def _get(self, path: str, params: Dict[str, Any] | None = None) -> Any:
        url = f"{BASE_URL}{path}"
        if params:
            url += f"?{urlencode(params)}"

        token = base64.b64encode(f"API_KEY:{self.api_key}".encode()).decode()
        req = Request(
            url,
            headers={
                "Authorization": f"Basic {token}",
                "Accept": "application/json",
            },
            method="GET",
        )

        try:
            with urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as exc:
            body = exc.read().decode(errors="ignore")
            raise RuntimeError(f"Intervals API HTTP {exc.code}: {body}") from exc
        except URLError as exc:
            raise RuntimeError(f"Intervals API connection error: {exc}") from exc

    def wellness(self, oldest: str, newest: str) -> List[Dict[str, Any]]:
        return self._get(
            f"/athlete/{self.athlete_id}/wellness",
            {"oldest": oldest, "newest": newest},
        )

    def activities(self, oldest: str, newest: str) -> List[Dict[str, Any]]:
        return self._get(
            f"/athlete/{self.athlete_id}/activities",
            {"oldest": oldest, "newest": newest},
        )

    def activity_streams(self, activity_id: str) -> List[Dict[str, Any]]:
        # Intervals stream endpoint is activity-scoped (not athlete-scoped).
        return self._get(f"/activity/{activity_id}/streams")


def normalize_wellness(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "date": row.get("id"),
        "updated": row.get("updated"),
        "weight_kg": row.get("weight"),
        "resting_hr": row.get("restingHR"),
        "hrv": row.get("hrv"),
        "sleep_seconds": row.get("sleepSecs"),
        "sleep_score": row.get("sleepScore"),
        "ctl": row.get("ctl"),
        "atl": row.get("atl"),
        "ramp_rate": row.get("rampRate"),
    }


def normalize_activity(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "type": row.get("type"),
        "start_date_local": row.get("start_date_local"),
        "moving_time_sec": row.get("moving_time"),
        "distance_m": row.get("distance"),
        "avg_hr": row.get("average_heartrate"),
        "max_hr": row.get("max_heartrate"),
        "weighted_avg_watts": row.get("icu_weighted_avg_watts"),
        "training_load": row.get("icu_training_load"),
        "intensity": row.get("icu_intensity"),
        "decoupling": row.get("decoupling"),
        "kj": (row.get("icu_joules") or 0) / 1000 if row.get("icu_joules") else None,
        "calories": row.get("calories"),
        "source_updated": row.get("updated"),
    }


def day_bounds(days: int = 1) -> tuple[str, str]:
    end = date.today()
    start = end.fromordinal(end.toordinal() - max(days - 1, 0))
    return start.isoformat(), end.isoformat()


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def freshness_status(updated_iso: str | None, max_age_minutes: int = 180) -> Dict[str, Any]:
    updated_dt = _parse_iso(updated_iso)
    if not updated_dt:
        return {
            "is_fresh": False,
            "reason": "missing_or_invalid_updated_timestamp",
            "updated": updated_iso,
            "age_minutes": None,
            "max_age_minutes": max_age_minutes,
        }

    now = datetime.now(timezone.utc)
    age_min = (now - updated_dt).total_seconds() / 60.0
    return {
        "is_fresh": age_min <= max_age_minutes,
        "reason": "ok" if age_min <= max_age_minutes else "stale",
        "updated": updated_dt.isoformat(),
        "age_minutes": round(age_min, 1),
        "max_age_minutes": max_age_minutes,
    }


def build_athlete_day(
    day: str,
    wellness_row: Dict[str, Any] | None,
    activities: List[Dict[str, Any]],
    max_age_minutes: int = 180,
) -> Dict[str, Any]:
    if not wellness_row:
        wellness = None
    elif "weight_kg" in wellness_row or "resting_hr" in wellness_row:
        wellness = wellness_row
    else:
        wellness = normalize_wellness(wellness_row)
    daily_activities = [a for a in activities if (a.get("start_date_local") or "").startswith(day)]

    total_calories = sum((a.get("calories") or 0) for a in daily_activities)
    total_kj = round(sum((a.get("kj") or 0.0) for a in daily_activities), 2)

    if daily_activities:
        weighted = [a.get("weighted_avg_watts") for a in daily_activities if a.get("weighted_avg_watts") is not None]
        avg_np = round(sum(weighted) / len(weighted), 1) if weighted else None
        total_load = round(sum((a.get("training_load") or 0) for a in daily_activities), 1)
    else:
        avg_np = None
        total_load = 0.0

    freshness = freshness_status((wellness or {}).get("updated"), max_age_minutes=max_age_minutes)

    return {
        "date": day,
        "source": "intervals.icu",
        "recovery": {
            "weight_kg": (wellness or {}).get("weight_kg"),
            "resting_hr": (wellness or {}).get("resting_hr"),
            "hrv": (wellness or {}).get("hrv"),
            "sleep_seconds": (wellness or {}).get("sleep_seconds"),
            "sleep_score": (wellness or {}).get("sleep_score"),
        },
        "load": {
            "ctl": (wellness or {}).get("ctl"),
            "atl": (wellness or {}).get("atl"),
            "ramp_rate": (wellness or {}).get("ramp_rate"),
            "daily_training_load": total_load,
        },
        "activity_summary": {
            "count": len(daily_activities),
            "total_calories": total_calories,
            "total_kj": total_kj,
            "avg_np": avg_np,
        },
        "freshness": freshness,
        "raw_refs": {
            "wellness_updated": (wellness or {}).get("updated"),
            "activity_ids": [a.get("id") for a in daily_activities],
        },
    }
