from __future__ import annotations

import unittest
from unittest.mock import patch

from peakflow.workout_review import build_latest_workout_review


class WorkoutReviewTests(unittest.TestCase):
    @patch("peakflow.workout_review._tp_workouts_via_script")
    @patch("peakflow.workout_review.IntervalsClient.from_env")
    def test_build_review_contract(self, mock_icu_from_env, mock_tp_script):
        mock_tp_script.return_value = [
            {
                "title": "Threshold 3x10",
                "tssPlanned": 85,
                "totalTimePlanned": 1.5,
                "structure": {
                    "structure": [
                        {
                            "steps": [
                                {
                                    "name": "10m threshold",
                                    "intensityClass": "work",
                                    "length": {"value": 600, "unit": "second"},
                                    "targets": [{"minValue": 85, "maxValue": 95}]
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
                        "icu_intensity": 81,
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
        self.assertIn(review["analysis"]["interval_matching"], ["matched", "pending"])
        self.assertIsInstance(review["analysis"]["intervals"], list)


if __name__ == "__main__":
    unittest.main()
