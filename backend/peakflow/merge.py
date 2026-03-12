from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


def canonical_source(source: str | None) -> str:
    if not source:
        return "unknown"
    s = source.lower().strip()
    if s.startswith("intervals"):
        return "intervals"
    if s.startswith("garmin"):
        return "garmin"
    if s.startswith("strava"):
        return "strava"
    if s.startswith("whoop"):
        return "whoop"
    return s


# Field-level priority map (evolves as new providers are onboarded)
FIELD_PRIORITY: Dict[str, List[str]] = {
    "recovery.weight_kg": ["garmin", "intervals", "strava"],
    "recovery.resting_hr": ["garmin", "intervals", "whoop"],
    "recovery.hrv": ["garmin", "whoop", "intervals"],
    "recovery.sleep_seconds": ["garmin", "whoop", "intervals"],
    "recovery.sleep_score": ["whoop", "garmin", "intervals"],
    "load.ctl": ["intervals", "strava", "garmin"],
    "load.atl": ["intervals", "strava", "garmin"],
    "load.ramp_rate": ["intervals", "strava", "garmin"],
    "load.daily_training_load": ["intervals", "strava", "garmin"],
    "activity_summary.count": ["intervals", "strava", "garmin"],
    "activity_summary.total_calories": ["garmin", "intervals", "strava"],
    "activity_summary.total_kj": ["intervals", "strava", "garmin"],
    "activity_summary.avg_np": ["intervals", "strava", "garmin"],
}

DEFAULT_SOURCE_PRIORITY = ["garmin", "intervals", "strava", "whoop", "unknown"]


def _distinct_values(candidates: List[Tuple[str, Any]]) -> List[Any]:
    vals = []
    for _, v in candidates:
        if v is None:
            continue
        if v not in vals:
            vals.append(v)
    return vals


def _pick_value(field: str, candidates: List[Tuple[str, Any]]) -> Tuple[Any, str | None, List[Dict[str, Any]]]:
    """Return (chosen_value, chosen_source, conflicts)."""
    non_null = [(s, v) for s, v in candidates if v is not None]
    if not non_null:
        return None, None, []

    pri = FIELD_PRIORITY.get(field, DEFAULT_SOURCE_PRIORITY)

    # stable source order according to field priority
    ordered = sorted(non_null, key=lambda sv: pri.index(sv[0]) if sv[0] in pri else len(pri) + 1)
    chosen_source, chosen_value = ordered[0]

    conflicts = []
    distinct = _distinct_values(non_null)
    if len(distinct) > 1:
        conflicts.append(
            {
                "field": field,
                "chosen": {"source": chosen_source, "value": chosen_value},
                "candidates": [{"source": s, "value": v} for s, v in non_null],
                "policy": pri,
            }
        )

    return chosen_value, chosen_source, conflicts


def merge_athlete_days(day: str, source_rows: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge one-day canonical athlete_day rows from multiple sources into a Gold payload.
    source_rows keys should be canonical source names: intervals/garmin/strava/whoop.
    """
    merged = {
        "date": day,
        "recovery": {},
        "load": {},
        "activity_summary": {},
    }
    provenance: Dict[str, str | None] = {}
    conflicts: List[Dict[str, Any]] = []

    fields = [
        "recovery.weight_kg",
        "recovery.resting_hr",
        "recovery.hrv",
        "recovery.sleep_seconds",
        "recovery.sleep_score",
        "load.ctl",
        "load.atl",
        "load.ramp_rate",
        "load.daily_training_load",
        "activity_summary.count",
        "activity_summary.total_calories",
        "activity_summary.total_kj",
        "activity_summary.avg_np",
    ]

    for field in fields:
        section, key = field.split(".", 1)
        candidates = []
        for src, row in source_rows.items():
            val = ((row.get(section) or {}).get(key)) if isinstance(row, dict) else None
            candidates.append((src, val))

        value, chosen_source, c = _pick_value(field, candidates)
        merged[section][key] = value
        provenance[field] = chosen_source
        conflicts.extend(c)

    # freshness: conservative rule -> fresh only if chosen source freshness is true (single source now)
    chosen_freshness = []
    for src, row in source_rows.items():
        f = row.get("freshness") or {}
        if isinstance(f, dict) and f.get("is_fresh") is not None:
            chosen_freshness.append((src, f))

    freshness = {
        "is_fresh": None,
        "reason": "no_freshness_data",
        "age_minutes": None,
        "max_age_minutes": None,
        "updated": None,
        "sources": {src: f for src, f in chosen_freshness},
    }
    if chosen_freshness:
        # use default source priority for overall readiness selection
        ordered = sorted(
            chosen_freshness,
            key=lambda sf: DEFAULT_SOURCE_PRIORITY.index(sf[0]) if sf[0] in DEFAULT_SOURCE_PRIORITY else len(DEFAULT_SOURCE_PRIORITY) + 1,
        )
        src, f = ordered[0]
        freshness = {
            "is_fresh": f.get("is_fresh"),
            "reason": f.get("reason", "ok" if f.get("is_fresh") else "stale"),
            "age_minutes": f.get("age_minutes"),
            "max_age_minutes": f.get("max_age_minutes"),
            "updated": f.get("updated"),
            "source": src,
            "sources": {s: x for s, x in chosen_freshness},
        }

    return {
        "date": day,
        "layer": "gold",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": sorted(source_rows.keys()),
        "merged": merged,
        "freshness": freshness,
        "provenance": provenance,
        "conflicts": conflicts,
        "conflict_count": len(conflicts),
    }


def append_conflicts_jsonl(path: Path, conflicts: List[Dict[str, Any]]) -> None:
    if not conflicts:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for c in conflicts:
            f.write(json.dumps(c) + "\n")
