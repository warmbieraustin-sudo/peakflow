#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SILVER = ROOT / "data" / "silver"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def require_keys(obj: dict, keys: list[str], label: str) -> list[str]:
    errors = []
    for k in keys:
        if k not in obj:
            errors.append(f"{label}: missing key '{k}'")
    return errors


def validate_athlete_day(path: Path) -> list[str]:
    errors: list[str] = []
    d = load_json(path)
    errors += require_keys(d, ["date", "source", "recovery", "load", "activity_summary", "freshness", "raw_refs"], str(path))
    if not isinstance(d.get("recovery"), dict):
        errors.append(f"{path}: recovery must be object")
    if not isinstance(d.get("freshness"), dict):
        errors.append(f"{path}: freshness must be object")
    else:
        f = d["freshness"]
        errors += require_keys(f, ["is_fresh", "reason", "updated", "age_minutes", "max_age_minutes"], f"{path}.freshness")
        if "is_fresh" in f and not isinstance(f["is_fresh"], bool):
            errors.append(f"{path}: freshness.is_fresh must be bool")
    return errors


def validate_activity_file(path: Path) -> list[str]:
    errors: list[str] = []
    arr = load_json(path)
    if not isinstance(arr, list):
        return [f"{path}: expected array"]
    required = [
        "id", "name", "type", "start_date_local", "moving_time_sec", "distance_m",
        "avg_hr", "max_hr", "weighted_avg_watts", "training_load", "intensity",
        "decoupling", "kj", "calories", "source_updated"
    ]
    for i, item in enumerate(arr):
        if not isinstance(item, dict):
            errors.append(f"{path}[{i}]: expected object")
            continue
        errors += require_keys(item, required, f"{path}[{i}]")
    return errors


def main() -> int:
    errors: list[str] = []

    ad_dir = SILVER / "athlete_day"
    act_dir = SILVER / "activities"

    for p in sorted(ad_dir.glob("*.json")):
        errors += validate_athlete_day(p)

    for p in sorted(act_dir.glob("*.json")):
        errors += validate_activity_file(p)

    if errors:
        print("VALIDATION_FAILED")
        for e in errors:
            print("-", e)
        return 1

    print("VALIDATION_OK")
    print(f"athlete_day_files={len(list(ad_dir.glob('*.json')))} activities_files={len(list(act_dir.glob('*.json')))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
