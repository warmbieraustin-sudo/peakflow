#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from peakflow.service import get_daily_metrics


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Morning-report readiness gate from PeakFlow daily metrics")
    p.add_argument("--day", type=str, default=None, help="Target day YYYY-MM-DD")
    p.add_argument("--fresh-minutes", type=int, default=180, help="Max allowed staleness")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    payload = get_daily_metrics(day=args.day, freshness_minutes=args.fresh_minutes)
    r = payload["readiness"]

    if r["recovery_fresh"]:
        print(f"READY: recovery freshness OK (age={r['age_minutes']}m <= {r['max_age_minutes']}m)")
        return 0

    print(
        "NOT_READY: recovery freshness stale "
        f"(age={r['age_minutes']}m > {r['max_age_minutes']}m, reason={r['reason']})"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
