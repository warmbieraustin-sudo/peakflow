#!/opt/homebrew/bin/python3
"""Pre-generate PeakFlow LLM/cache endpoints to keep UI fast.
Runs safely multiple times per day.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8787"
ATHLETE_ID = "default"


def get(path: str) -> tuple[int, dict]:
    req = Request(f"{BASE}{path}", method="GET")
    with urlopen(req, timeout=45) as r:
        body = r.read().decode("utf-8")
        return r.status, json.loads(body) if body else {}


def main() -> int:
    today = date.today().isoformat()
    calls = [
        f"/api/alpha/llm/debrief/today?{urlencode({'athleteId': ATHLETE_ID})}",
        f"/api/alpha/planner/horizon?{urlencode({'athleteId': ATHLETE_ID, 'sport': 'cycling', 'coachMode': 'false'})}",
        f"/api/alpha/llm/explain-workout?{urlencode({'athleteId': ATHLETE_ID, 'sport': 'cycling', 'coachMode': 'false'})}",
        f"/api/alpha/llm/workout-analysis/today?{urlencode({'athleteId': ATHLETE_ID})}",
        f"/api/alpha/llm/analysis?{urlencode({'athleteId': ATHLETE_ID})}",
        f"/api/alpha/llm/weekly-plan?{urlencode({'athleteId': ATHLETE_ID, 'startDate': today})}",
    ]

    ok = 0
    failed = 0
    for p in calls:
        try:
            status, payload = get(p)
            if 200 <= status < 300 and payload.get("ok", True):
                ok += 1
                print(f"✅ {p} ({status})")
            else:
                failed += 1
                print(f"❌ {p} ({status}) {payload}")
        except Exception as exc:
            failed += 1
            print(f"❌ {p} ({exc})")

    print(f"\nPrewarm complete: {ok} ok, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
