#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from peakflow.storage import latest_athlete_day


if __name__ == "__main__":
    silver_base = Path(__file__).resolve().parents[1] / "data" / "silver"
    row = latest_athlete_day(silver_base)
    if not row:
        print("NO_DATA")
        raise SystemExit(1)
    print(json.dumps(row, indent=2))
