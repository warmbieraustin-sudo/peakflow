#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from peakflow.service import get_daily_metrics


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PeakFlow single-entry daily metrics fetch")
    p.add_argument("--day", type=str, default=None, help="Target day YYYY-MM-DD (default: today)")
    p.add_argument("--fresh-minutes", type=int, default=180, help="Freshness threshold in minutes")
    p.add_argument("--compact", action="store_true", help="Print compact summary before JSON")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = get_daily_metrics(day=args.day, freshness_minutes=args.fresh_minutes)

    if args.compact:
        ad = payload["athlete_day"]
        r = payload["readiness"]
        print(
            f"{payload['date']} | fresh={r['recovery_fresh']} age={r['age_minutes']}m "
            f"weight={ad['recovery']['weight_kg']}kg RHR={ad['recovery']['resting_hr']} HRV={ad['recovery']['hrv']}"
        )

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
