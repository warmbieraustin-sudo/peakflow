from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def _write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    return path


def persist_silver(
    base_dir: Path,
    athlete_days: List[Dict[str, Any]],
    activities_by_day: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, List[str]]:
    """
    Persist normalized Silver-layer artifacts:
      - athlete_day/YYYY-MM-DD.json
      - activities/YYYY-MM-DD.json
    """
    out = {"athlete_day": [], "activities": []}

    for row in athlete_days:
        day = row["date"]
        p = base_dir / "athlete_day" / f"{day}.json"
        _write_json(p, row)
        out["athlete_day"].append(str(p))

    for day, items in activities_by_day.items():
        p = base_dir / "activities" / f"{day}.json"
        _write_json(p, items)
        out["activities"].append(str(p))

    return out
