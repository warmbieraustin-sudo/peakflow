#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

from peakflow.intervals import (
    IntervalsClient,
    build_athlete_day,
    day_bounds,
    normalize_activity,
    normalize_wellness,
)
from peakflow.storage import persist_silver


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch Intervals.icu wellness + activities snapshot")
    p.add_argument("--days", type=int, default=1, help="How many trailing days to fetch")
    p.add_argument("--oldest", type=str, default=None, help="Start date YYYY-MM-DD")
    p.add_argument("--newest", type=str, default=None, help="End date YYYY-MM-DD")
    p.add_argument("--write", action="store_true", help="Write Bronze JSON snapshot to backend/data/snapshots")
    p.add_argument(
        "--silver",
        action="store_true",
        help="Persist normalized silver artifacts to backend/data/silver",
    )
    p.add_argument(
        "--fresh-minutes",
        type=int,
        default=180,
        help="Freshness threshold (minutes) for athlete_day.freshness",
    )
    return p.parse_args()


def iter_days(oldest: str, newest: str) -> List[str]:
    d0 = datetime.fromisoformat(oldest).date()
    d1 = datetime.fromisoformat(newest).date()
    days = []
    cur = d0
    while cur <= d1:
        days.append(cur.isoformat())
        cur += timedelta(days=1)
    return days


def main() -> None:
    args = parse_args()
    if args.oldest and args.newest:
        oldest, newest = args.oldest, args.newest
    else:
        oldest, newest = day_bounds(args.days)

    client = IntervalsClient.from_env()

    wellness_rows_raw = client.wellness(oldest, newest)
    activity_rows_raw = client.activities(oldest, newest)

    wellness_rows = [normalize_wellness(r) for r in wellness_rows_raw]
    activity_rows = [normalize_activity(r) for r in activity_rows_raw]

    wellness_by_day: Dict[str, dict] = {r["date"]: r for r in wellness_rows if r.get("date")}
    activities_by_day: Dict[str, List[dict]] = {}
    for a in activity_rows:
        day = (a.get("start_date_local") or "")[:10]
        if not day:
            continue
        activities_by_day.setdefault(day, []).append(a)

    day_list = iter_days(oldest, newest)
    athlete_days = [
        build_athlete_day(
            day,
            wellness_row=wellness_by_day.get(day),
            activities=activity_rows,
            max_age_minutes=args.fresh_minutes,
        )
        for day in day_list
    ]

    bronze_snapshot = {
        "source": "intervals.icu",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "range": {"oldest": oldest, "newest": newest},
        "wellness": wellness_rows,
        "activities": activity_rows,
    }

    if args.write:
        out_dir = Path(__file__).resolve().parents[1] / "data" / "snapshots"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"intervals_snapshot_{oldest}_{newest}.json"
        out_file.write_text(json.dumps(bronze_snapshot, indent=2))
        print(f"wrote bronze snapshot: {out_file}")

    silver_paths = None
    if args.silver:
        silver_base = Path(__file__).resolve().parents[1] / "data" / "silver"
        silver_paths = persist_silver(silver_base, athlete_days, activities_by_day)
        print("wrote silver artifacts:")
        print(f"  athlete_day: {len(silver_paths.get('athlete_day', []))} files")
        print(f"  activities: {len(silver_paths.get('activities', []))} files")
        if silver_paths.get("index"):
            print(f"  index: {silver_paths['index']}")

    print(f"Range: {oldest} → {newest}")
    print(f"Wellness rows: {len(wellness_rows)} | Activities: {len(activity_rows)}")

    if athlete_days:
        latest = athlete_days[-1]
        f = latest["freshness"]
        print(
            "Latest athlete_day: "
            f"date={latest['date']} "
            f"weight={latest['recovery']['weight_kg']}kg "
            f"RHR={latest['recovery']['resting_hr']} HRV={latest['recovery']['hrv']} "
            f"fresh={f['is_fresh']} age_min={f['age_minutes']}"
        )

    if activity_rows:
        a = activity_rows[-1]
        print(
            "Latest activity: "
            f"{a['name']} ({a['type']}) "
            f"NP={a['weighted_avg_watts']}W TL={a['training_load']} "
            f"decoupling={a['decoupling']} cal={a['calories']}"
        )

    output = {
        "bronze": bronze_snapshot,
        "silver": {
            "athlete_day": athlete_days,
            "activities_by_day": activities_by_day,
        },
        "silver_paths": silver_paths,
    }

    print("\nJSON:\n" + json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
