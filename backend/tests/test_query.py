from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from peakflow.query import build_consumer_contract, get_day_bundle, get_range


class QueryLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        (self.base / "athlete_day").mkdir(parents=True, exist_ok=True)
        (self.base / "activities").mkdir(parents=True, exist_ok=True)

        day1 = {
            "date": "2026-03-10",
            "source": "intervals.icu",
            "recovery": {"weight_kg": 67.1, "resting_hr": 46, "hrv": 90, "sleep_seconds": 30000, "sleep_score": 82},
            "load": {"ctl": 53, "atl": 64, "ramp_rate": 2.8, "daily_training_load": 72},
            "activity_summary": {"count": 1, "total_calories": 700, "total_kj": 720.5, "avg_np": 180},
            "freshness": {"is_fresh": True, "reason": "ok", "updated": "2026-03-10T14:00:00+00:00", "age_minutes": 30, "max_age_minutes": 180},
            "raw_refs": {"wellness_updated": "2026-03-10T14:00:00+00:00", "activity_ids": ["a1"]},
        }
        day2 = {
            "date": "2026-03-11",
            "source": "intervals.icu",
            "recovery": {"weight_kg": 66.9, "resting_hr": 44, "hrv": 95, "sleep_seconds": 30720, "sleep_score": 86},
            "load": {"ctl": 54, "atl": 67, "ramp_rate": 3.3, "daily_training_load": 55},
            "activity_summary": {"count": 1, "total_calories": 944, "total_kj": 988.6, "avg_np": 138},
            "freshness": {"is_fresh": True, "reason": "ok", "updated": "2026-03-11T14:00:00+00:00", "age_minutes": 20, "max_age_minutes": 180},
            "raw_refs": {"wellness_updated": "2026-03-11T14:00:00+00:00", "activity_ids": ["a2"]},
        }

        (self.base / "athlete_day" / "2026-03-10.json").write_text(json.dumps(day1))
        (self.base / "athlete_day" / "2026-03-11.json").write_text(json.dumps(day2))

        (self.base / "activities" / "2026-03-10.json").write_text(json.dumps([{"id": "a1", "calories": 700}]))
        (self.base / "activities" / "2026-03-11.json").write_text(json.dumps([{"id": "a2", "calories": 944}]))

        # optional index for latest lookup
        (self.base / "index.json").write_text(json.dumps({"latest_day": "2026-03-11"}))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_get_day_bundle(self):
        bundle = get_day_bundle(self.base, "2026-03-10")
        self.assertIsNotNone(bundle)
        self.assertEqual(bundle["date"], "2026-03-10")
        self.assertEqual(len(bundle["activities"]), 1)

    def test_get_range(self):
        out = get_range(self.base, "2026-03-10", "2026-03-11")
        self.assertEqual(out["count"], 2)

    def test_consumer_contract_latest(self):
        payload = build_consumer_contract(self.base)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["date"], "2026-03-11")
        self.assertEqual(payload["activity_count"], 1)
        self.assertTrue(payload["fresh"])


if __name__ == "__main__":
    unittest.main()
