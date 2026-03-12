from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    return path


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _available_days(dir_path: Path) -> List[str]:
    if not dir_path.exists():
        return []
    return sorted(p.stem for p in dir_path.glob("*.json"))


def build_silver_index(base_dir: Path) -> Dict[str, Any]:
    athlete_day_dir = base_dir / "athlete_day"
    activities_dir = base_dir / "activities"

    athlete_days = _available_days(athlete_day_dir)
    activity_days = _available_days(activities_dir)

    latest_day = athlete_days[-1] if athlete_days else None
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latest_day": latest_day,
        "athlete_day_count": len(athlete_days),
        "activity_day_count": len(activity_days),
        "athlete_days": athlete_days,
        "activity_days": activity_days,
    }


def write_silver_index(base_dir: Path) -> Path:
    index = build_silver_index(base_dir)
    return _write_json(base_dir / "index.json", index)


def persist_silver(
    base_dir: Path,
    athlete_days: List[Dict[str, Any]],
    activities_by_day: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """
    Persist normalized Silver-layer artifacts with deterministic overwrite semantics:
      - athlete_day/YYYY-MM-DD.json
      - activities/YYYY-MM-DD.json
      - index.json

    Overwrite rule:
      If a day file already exists, it is fully replaced by the latest normalization output.
    """
    out: Dict[str, Any] = {"athlete_day": [], "activities": []}

    for row in sorted(athlete_days, key=lambda x: x["date"]):
        day = row["date"]
        p = base_dir / "athlete_day" / f"{day}.json"
        _write_json(p, row)
        out["athlete_day"].append(str(p))

    for day in sorted(activities_by_day.keys()):
        p = base_dir / "activities" / f"{day}.json"
        _write_json(p, activities_by_day[day])
        out["activities"].append(str(p))

    index_path = write_silver_index(base_dir)
    out["index"] = str(index_path)
    return out


def load_athlete_day(base_dir: Path, day: str) -> Dict[str, Any] | None:
    p = base_dir / "athlete_day" / f"{day}.json"
    if not p.exists():
        return None
    return _read_json(p)


def latest_athlete_day(base_dir: Path) -> Dict[str, Any] | None:
    index_path = base_dir / "index.json"
    if index_path.exists():
        idx = _read_json(index_path)
        latest_day = idx.get("latest_day")
        if latest_day:
            return load_athlete_day(base_dir, latest_day)

    # fallback if index absent
    days = _available_days(base_dir / "athlete_day")
    if not days:
        return None
    return load_athlete_day(base_dir, days[-1])
