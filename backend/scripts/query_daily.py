#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from peakflow.query import build_consumer_contract


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Query one day consumer contract from silver storage")
    p.add_argument("--day", type=str, default=None, help="Target day YYYY-MM-DD (default: latest)")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    silver = Path(__file__).resolve().parents[1] / "data" / "silver"
    payload = build_consumer_contract(silver, day=args.day)
    if not payload:
        print("NO_DATA")
        raise SystemExit(1)
    print(json.dumps(payload, indent=2))
