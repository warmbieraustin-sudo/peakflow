#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from peakflow.merge import append_conflicts_jsonl, canonical_source, merge_athlete_days
from peakflow.storage import latest_athlete_day, load_athlete_day


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build PeakFlow Gold daily payload from Silver sources")
    p.add_argument("--day", type=str, default=None, help="Target day YYYY-MM-DD (default: latest available)")
    p.add_argument("--write", action="store_true", help="Write output to backend/data/gold/daily")
    p.add_argument("--log-conflicts", action="store_true", help="Append conflicts to backend/data/silver/conflicts/YYYY-MM-DD.jsonl")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    root = Path(__file__).resolve().parents[1]
    silver_base = root / "data" / "silver"
    day = args.day

    row = load_athlete_day(silver_base, day) if day else latest_athlete_day(silver_base)
    if not row:
        print("NO_SILVER_DATA")
        raise SystemExit(1)

    day = row["date"]
    source_rows = {canonical_source(row.get("source")): row}

    gold = merge_athlete_days(day, source_rows)

    if args.write:
        out_dir = root / "data" / "gold" / "daily"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{day}.json"
        out_file.write_text(json.dumps(gold, indent=2))
        print(f"wrote {out_file}")

    if args.log_conflicts:
        conflicts_path = silver_base / "conflicts" / f"{day}.jsonl"
        append_conflicts_jsonl(conflicts_path, gold.get("conflicts", []))
        print(f"conflicts_appended={len(gold.get('conflicts', []))} path={conflicts_path}")

    print(
        f"Gold day={day} sources={gold['sources']} fresh={gold['freshness']['is_fresh']} "
        f"conflicts={gold['conflict_count']}"
    )
    print(json.dumps(gold, indent=2))


if __name__ == "__main__":
    main()
