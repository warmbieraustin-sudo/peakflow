from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from peakflow.pwa_contract import build_alpha_shell_payload


class PwaContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        (self.base / "athlete_day").mkdir(parents=True, exist_ok=True)
        (self.base / "activities").mkdir(parents=True, exist_ok=True)

        day = {
            "date": "2026-03-12",
            "source": "intervals.icu",
            "recovery": {"weight_kg": 66.8, "resting_hr": 41, "hrv": 97, "sleep_seconds": 28260, "sleep_score": 97},
            "load": {"ctl": 53.2, "atl": 58.3, "ramp_rate": 2.8, "daily_training_load": 0},
            "activity_summary": {"count": 0, "total_calories": 0, "total_kj": 0, "avg_np": None},
            "freshness": {"is_fresh": True, "reason": "ok", "updated": "2026-03-12T12:24:00+00:00", "age_minutes": 10, "max_age_minutes": 180},
            "raw_refs": {"wellness_updated": "2026-03-12T12:24:00+00:00", "activity_ids": []},
        }
        (self.base / "athlete_day" / "2026-03-12.json").write_text(json.dumps(day))
        (self.base / "activities" / "2026-03-12.json").write_text(json.dumps([]))
        (self.base / "index.json").write_text(json.dumps({"latest_day": "2026-03-12"}))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_build_payload(self):
        p = build_alpha_shell_payload(self.base)
        self.assertIsNotNone(p)
        self.assertIn("screens", p)
        self.assertIn("morning_brief", p["screens"])
        self.assertIn("recovery_load", p["screens"])
        self.assertIn("chat_context", p["screens"])


if __name__ == "__main__":
    unittest.main()
