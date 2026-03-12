#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from peakflow.workout_review import build_latest_workout_review


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build latest workout review payload")
    p.add_argument("--day", type=str, default=None, help="Target day YYYY-MM-DD")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    payload = build_latest_workout_review(day=args.day)
    print(json.dumps(payload, indent=2))
