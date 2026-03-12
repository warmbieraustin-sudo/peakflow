from __future__ import annotations

import unittest

from peakflow.planner import SUPPORTED_SPORTS, build_daily_recommendation, validate_plan_schema


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
        self.assertIn("next_action", rec)
        self.assertIn("plan_validation", rec)

    def test_focus_sport_sets_single_sport_mode(self):
        rec = build_daily_recommendation({}, "cycling", focus_sport="cycling")
        self.assertEqual(rec["athlete_mode"], "single_sport")
        self.assertIn("cycling", SUPPORTED_SPORTS)

    def test_feedback_adjusts_recommendation(self):
        last_review = {
            "analysis": {
                "score": 40,
                "confidence": "low",
                "reason_codes": ["LOW_COMPLIANCE"],
            }
        }
        rec = build_daily_recommendation({}, "running", focus_sport="running", last_review=last_review)
        self.assertEqual(rec["intensity_band"], "easy")
        self.assertEqual(rec["next_action"], "reduce_load_and_focus_recovery")
        self.assertTrue(rec["feedback_summary"]["used"])

    def test_plan_schema_validation(self):
        valid, reasons = validate_plan_schema(
            {
                "sport_type": "running",
                "title": "Run Session",
                "blocks": [
                    {
                        "label": "steady",
                        "duration_sec": 1800,
                        "target_type": "rpe",
                        "target_low": 4,
                        "target_high": 5,
                    }
                ],
            }
        )
        self.assertTrue(valid)
        self.assertEqual(reasons, [])

        invalid, invalid_reasons = validate_plan_schema({"sport_type": "unknown", "title": "", "blocks": []})
        self.assertFalse(invalid)
        self.assertTrue(len(invalid_reasons) >= 1)


if __name__ == "__main__":
    unittest.main()
