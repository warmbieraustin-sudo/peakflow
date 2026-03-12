#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "app-state" / "planner_state.json"
FEEDBACK_PATH = ROOT / "data" / "app-state" / "reco_feedback.jsonl"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _load_feedback_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def build_snapshot() -> dict:
    state = _load_json(STATE_PATH, {"athletes": {}})
    athletes = (state.get("athletes") or {})
    rows = _load_feedback_rows(FEEDBACK_PATH)

    relevance = [r.get("relevance") for r in rows if isinstance(r.get("relevance"), (int, float))]
    perceived = Counter(r.get("perceived") for r in rows if r.get("perceived"))
    by_athlete = Counter(r.get("athlete_id") for r in rows if r.get("athlete_id"))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "athlete_count": len(athletes),
        "coach_mode_enabled_count": sum(1 for a in athletes.values() if a.get("coach_mode") is True),
        "feedback": {
            "count": len(rows),
            "avg_relevance": round(sum(relevance) / len(relevance), 2) if relevance else None,
            "perceived_counts": dict(perceived),
            "rows_by_athlete": dict(by_athlete),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate PeakFlow alpha metrics snapshot")
    ap.add_argument("--write", action="store_true", help="Write snapshot to data/app-state/metrics/latest.json")
    args = ap.parse_args()

    snapshot = build_snapshot()
    print(json.dumps(snapshot, indent=2))

    if args.write:
        out = ROOT / "data" / "app-state" / "metrics" / "latest.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(snapshot, indent=2))
        print(f"wrote {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
