from __future__ import annotations

import unittest
from unittest.mock import patch

from peakflow.workout_review import build_latest_workout_review, evaluate_plan_execution


class WorkoutReviewTests(unittest.TestCase):
    @patch("peakflow.workout_review._tp_workouts_via_script")
    @patch("peakflow.workout_review.IntervalsClient.from_env")
    def test_build_review_contract(self, mock_icu_from_env, mock_tp_script):
        mock_tp_script.return_value = [
            {
                "title": "Threshold 3x10",
                "tssPlanned": 85,
                "totalTimePlanned": 3600,
                "structure": {
                    "structure": [
                        {
                            "steps": [
                                {
                                    "name": "10m threshold",
                                    "intensityClass": "work",
                                    "length": {"value": 600, "unit": "second"},
                                    "targets": [{"minValue": 85, "maxValue": 95}],
                                }
                            ]
                        }
                    ]
                },
            }
        ]

        class _ICU:
            def activities(self, oldest, newest):
                return [
                    {
                        "id": "i123",
                        "name": "Zwift",
                        "start_date_local": f"{oldest}T07:00:00",
                        "moving_time": 3600,
                        "average_watts": 180,
                        "icu_weighted_avg_watts": 205,
                        "average_heartrate": 148,
                        "icu_training_load": 72,
                        "icu_intensity": 88,
                        "decoupling": 2.4,
                        "calories": 790,
                    }
                ]

        mock_icu_from_env.return_value = _ICU()

        review = build_latest_workout_review(day="2026-03-12")

        self.assertEqual(review["date"], "2026-03-12")
        self.assertEqual(review["prescription"]["status"], "ok")
        self.assertEqual(review["execution"]["status"], "ok")
        self.assertTrue(review["analysis"]["prescription_available"])
        self.assertTrue(review["analysis"]["execution_available"])
        self.assertIn(review["analysis"]["interval_matching"], ["matched", "partial", "missed"])
        self.assertIn(review["analysis"]["matching_tier"], ["power_hr", "hr_only", "duration_only", "none"])
        self.assertIsInstance(review["analysis"]["reason_codes"], list)
        self.assertIsInstance(review["analysis"]["intervals"], list)

    def test_llm_plan_duration_only_tier(self):
        llm_plan = {
            "source": "llm",
            "title": "Endurance 60",
            "planned_duration_sec": 3600,
            "intervals": [
                {
                    "label": "steady",
                    "type": "endurance",
                    "duration_sec": 3600,
                    "target_type": "rpe",
                    "target_low": 3,
                    "target_high": 4,
                }
            ],
        }
        execution = {
            "moving_time_sec": 3400,
            # intentionally sparse: no HR/power
        }
        analysis = evaluate_plan_execution(llm_plan, execution)

        self.assertEqual(analysis["matching_tier"], "duration_only")
        self.assertEqual(analysis["confidence"], "low")
        self.assertIsNotNone(analysis["score"])
        self.assertIn("DURATION_ONLY_MATCH", analysis["reason_codes"])

    def test_stream_window_matching(self):
        plan = {
            "source": "llm",
            "title": "2x5 threshold",
            "planned_duration_sec": 600,
            "intervals": [
                {"label": "work1", "type": "work", "duration_sec": 300, "target_type": "power_pct_ftp", "target_low": 90, "target_high": 95},
                {"label": "work2", "type": "work", "duration_sec": 300, "target_type": "power_pct_ftp", "target_low": 90, "target_high": 95},
            ],
        }
        execution = {
            "moving_time_sec": 600,
            "weighted_avg_watts": 240,
            "avg_hr": 150,
            "intensity": 92,
            "ftp": 250,
        }
        streams = [
            {"type": "time", "data": list(range(600))},
            {"type": "watts", "data": [230] * 300 + [240] * 300},
            {"type": "heartrate", "data": [145] * 300 + [152] * 300},
        ]

        analysis = evaluate_plan_execution(plan, execution, streams=streams)
        self.assertEqual(analysis["matching_tier"], "power_hr")
        self.assertIn("STREAM_WINDOW_MATCH", analysis["reason_codes"])
        self.assertEqual(len(analysis["intervals"]), 2)
        self.assertIn(analysis["interval_matching"], ["matched", "partial", "missed"])


if __name__ == "__main__":
    unittest.main()
