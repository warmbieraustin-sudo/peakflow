#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from peakflow.intervals import IntervalsClient, day_bounds, normalize_activity, normalize_wellness


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch Intervals.icu wellness + activities snapshot")
    p.add_argument("--days", type=int, default=1, help="How many trailing days to fetch")
    p.add_argument("--oldest", type=str, default=None, help="Start date YYYY-MM-DD")
    p.add_argument("--newest", type=str, default=None, help="End date YYYY-MM-DD")
    p.add_argument("--write", action="store_true", help="Write JSON snapshot to backend/data/snapshots")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.oldest and args.newest:
        oldest, newest = args.oldest, args.newest
    else:
        oldest, newest = day_bounds(args.days)

    client = IntervalsClient.from_env()

    wellness_rows = client.wellness(oldest, newest)
    activity_rows = client.activities(oldest, newest)

    wellness = [normalize_wellness(r) for r in wellness_rows]
    activities = [normalize_activity(r) for r in activity_rows]

    snapshot = {
        "source": "intervals.icu",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "range": {"oldest": oldest, "newest": newest},
        "wellness": wellness,
        "activities": activities,
    }

    if args.write:
        out_dir = Path(__file__).resolve().parents[1] / "data" / "snapshots"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"intervals_snapshot_{oldest}_{newest}.json"
        out_file.write_text(json.dumps(snapshot, indent=2))
        print(f"wrote {out_file}")

    # concise operator summary first
    print(f"Range: {oldest} → {newest}")
    print(f"Wellness rows: {len(wellness)} | Activities: {len(activities)}")

    if wellness:
        w = wellness[-1]
        print(
            "Latest wellness: "
            f"date={w['date']} weight={w['weight_kg']}kg "
            f"RHR={w['resting_hr']} HRV={w['hrv']} updated={w['updated']}"
        )

    if activities:
        a = activities[-1]
        print(
            "Latest activity: "
            f"{a['name']} ({a['type']}) "
            f"NP={a['weighted_avg_watts']}W TL={a['training_load']} "
            f"decoupling={a['decoupling']} cal={a['calories']}"
        )

    print("\nJSON:\n" + json.dumps(snapshot, indent=2))


if __name__ == "__main__":
    main()
