#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from peakflow.query import get_range


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Query a date range from silver storage")
    p.add_argument("--oldest", required=True, type=str, help="Start day YYYY-MM-DD")
    p.add_argument("--newest", required=True, type=str, help="End day YYYY-MM-DD")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    silver = Path(__file__).resolve().parents[1] / "data" / "silver"
    payload = get_range(silver, args.oldest, args.newest)
    print(json.dumps(payload, indent=2))
