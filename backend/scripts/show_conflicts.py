#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Show PeakFlow merge conflicts from silver conflict logs")
    p.add_argument("--day", type=str, default=None, help="Target day YYYY-MM-DD (default: latest by filename)")
    p.add_argument("--limit", type=int, default=10, help="Max conflict lines to print")
    return p.parse_args()


def main() -> int:
    base = Path(__file__).resolve().parents[1] / "data" / "silver" / "conflicts"
    if not base.exists():
        print("No conflicts logged yet.")
        return 0

    if args.day:
        target = base / f"{args.day}.jsonl"
    else:
        files = sorted(base.glob("*.jsonl"))
        if not files:
            print("NO_CONFLICT_FILES")
            return 1
        target = files[-1]

    if not target.exists():
        print(f"NO_FILE {target}")
        return 1

    lines = [ln for ln in target.read_text().splitlines() if ln.strip()]
    total = len(lines)
    print(f"file={target} total_conflicts={total}")

    for ln in lines[-args.limit:]:
        try:
            obj = json.loads(ln)
        except Exception:
            print(ln)
            continue
        field = obj.get("field")
        chosen = (obj.get("chosen") or {}).get("value")
        chosen_src = (obj.get("chosen") or {}).get("source")
        print(f"- field={field} chosen={chosen} source={chosen_src}")

    return 0


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(main())
