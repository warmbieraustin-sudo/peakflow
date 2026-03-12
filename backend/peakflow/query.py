from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .storage import latest_athlete_day


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def get_athlete_day(base_dir: Path, day: str) -> Dict[str, Any] | None:
    path = base_dir / "athlete_day" / f"{day}.json"
    if not path.exists():
        return None
    return _read_json(path)


def get_activities_for_day(base_dir: Path, day: str) -> List[Dict[str, Any]]:
    path = base_dir / "activities" / f"{day}.json"
    if not path.exists():
        return []
    data = _read_json(path)
    return data if isinstance(data, list) else []


def list_days(base_dir: Path) -> List[str]:
    p = base_dir / "athlete_day"
    if not p.exists():
        return []
    return sorted(x.stem for x in p.glob("*.json"))


def get_day_bundle(base_dir: Path, day: str) -> Dict[str, Any] | None:
    athlete_day = get_athlete_day(base_dir, day)
    if athlete_day is None:
        return None

    return {
        "date": day,
        "athlete_day": athlete_day,
        "activities": get_activities_for_day(base_dir, day),
    }


def get_range(base_dir: Path, oldest: str, newest: str) -> Dict[str, Any]:
    days = [d for d in list_days(base_dir) if oldest <= d <= newest]
    rows = []
    for d in days:
        bundle = get_day_bundle(base_dir, d)
        if bundle:
            rows.append(bundle)
    return {
        "oldest": oldest,
        "newest": newest,
        "count": len(rows),
        "days": rows,
    }


def build_consumer_contract(base_dir: Path, day: str | None = None) -> Dict[str, Any] | None:
    """
    Stable downstream contract for morning-report/workout-analysis consumers.
    This intentionally keeps field names compact and consistent across future sources.
    """
    if day:
        bundle = get_day_bundle(base_dir, day)
    else:
        ad = latest_athlete_day(base_dir)
        if not ad:
            return None
        bundle = get_day_bundle(base_dir, ad["date"])

    if not bundle:
        return None

    ad = bundle["athlete_day"]
    activities = bundle["activities"]

    return {
        "date": bundle["date"],
        "fresh": (ad.get("freshness") or {}).get("is_fresh"),
        "freshness_age_minutes": (ad.get("freshness") or {}).get("age_minutes"),
        "recovery": ad.get("recovery") or {},
        "load": ad.get("load") or {},
        "activity_summary": ad.get("activity_summary") or {},
        "activity_count": len(activities),
        "activities": activities,
    }
