from __future__ import annotations

import unittest

from peakflow.planner import SUPPORTED_SPORTS, build_daily_recommendation


class PlannerTests(unittest.TestCase):
    def test_recommendation_uses_selected_sport(self):
        shell = {
            "screens": {
                "morning_brief": {
                    "headline": {"fresh": True},
                    "quick_load": {"daily_training_load": 20.0},
                }
            }
        }
        rec = build_daily_recommendation(shell, "running", focus_sport="cycling")
        self.assertEqual(rec["selected_sport"], "running")
        self.assertEqual(rec["athlete_mode"], "multi_sport")
        self.assertEqual(rec["plan"]["sport_type"], "running")
        self.assertTrue(len(rec["plan"]["blocks"]) >= 1)

    def test_focus_sport_sets_single_sport_mode(self):
        rec = build_daily_recommendation({}, "cycling", focus_sport="cycling")
        self.assertEqual(rec["athlete_mode"], "single_sport")
        self.assertIn("cycling", SUPPORTED_SPORTS)


if __name__ == "__main__":
    unittest.main()
