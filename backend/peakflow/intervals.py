from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import date
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
    }


def day_bounds(days: int = 1) -> tuple[str, str]:
    end = date.today()
    start = end.fromordinal(end.toordinal() - max(days - 1, 0))
    return start.isoformat(), end.isoformat()
