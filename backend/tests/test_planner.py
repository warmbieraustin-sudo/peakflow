from __future__ import annotations

import unittest

from unittest.mock import patch

from peakflow.planner import (
    SUPPORTED_SPORTS,
    build_coach_mode_horizon,
    build_coach_mode_recommendation,
    build_daily_recommendation,
    build_horizon_plan,
    decide_phase,
    validate_plan_schema,
)


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

    def test_explicit_athlete_feedback_overrides(self):
        last_review = {"analysis": {"score": 95, "confidence": "high", "reason_codes": []}}
        rec = build_daily_recommendation(
            {"screens": {"morning_brief": {"headline": {"fresh": True}, "quick_load": {"daily_training_load": 10}}}},
            "cycling",
            focus_sport="cycling",
            last_review=last_review,
            athlete_feedback="hard",
        )
        self.assertEqual(rec["intensity_band"], "easy")
        self.assertEqual(rec["modification_reason"], "athlete_reported_too_hard")

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

    def test_decide_phase_deload_trigger(self):
        phase = decide_phase({"last7_load": 700, "prev21_weekly_avg_load": 400, "hard_sessions_last7": 5}, fresh=False)
        self.assertEqual(phase["phase"], "deload")

    def test_horizon_plan_shape(self):
        activities = [
            {"start_date_local": "2026-03-01T07:00:00", "icu_training_load": 60, "icu_intensity": 82},
            {"start_date_local": "2026-03-02T07:00:00", "icu_training_load": 70, "icu_intensity": 85},
            {"start_date_local": "2026-03-03T07:00:00", "icu_training_load": 65, "icu_intensity": 88},
            {"start_date_local": "2026-03-04T07:00:00", "icu_training_load": 60, "icu_intensity": 81},
            {"start_date_local": "2026-03-05T07:00:00", "icu_training_load": 75, "icu_intensity": 86},
            {"start_date_local": "2026-03-06T07:00:00", "icu_training_load": 80, "icu_intensity": 84},
            {"start_date_local": "2026-03-07T07:00:00", "icu_training_load": 50, "icu_intensity": 65},
        ]
        horizon = build_horizon_plan({}, "cycling", focus_sport="cycling", recent_activities=activities)
        self.assertEqual(horizon["horizon"]["firm_days"], 7)
        self.assertEqual(horizon["horizon"]["soft_days"], 28)
        self.assertEqual(len(horizon["days"]), 28)
        self.assertTrue(all("plan" in d for d in horizon["days"]))

    @patch("peakflow.planner._tp_workouts_via_script")
    def test_coach_mode_tp_first(self, mock_tp):
        mock_tp.return_value = [
            {
                "workoutId": 123,
                "title": "Coach Endurance Ride",
                "workoutTypeValueId": 2,
                "description": "Stay easy",
                "tssPlanned": 45,
                "structure": {
                    "structure": [
                        {
                            "steps": [
                                {
                                    "name": "Active",
                                    "length": {"unit": "second", "value": 1800},
                                    "targets": [{"minValue": 60, "maxValue": 70}],
                                }
                            ]
                        }
                    ]
                },
            }
        ]

        rec = build_coach_mode_recommendation({}, "cycling", focus_sport="cycling", day="2026-03-12")
        self.assertTrue(rec["coach_mode"])
        self.assertEqual(rec["plan_source"], "trainingpeaks")
        self.assertTrue(rec["non_destructive_overlay"])
        self.assertEqual((rec["plan"] or {}).get("title"), "Coach Endurance Ride")
        self.assertIn("peakflow_overlay", rec)

    @patch("peakflow.planner._tp_workouts_range_via_script")
    def test_coach_mode_horizon_tp_overlay(self, mock_tp_range):
        mock_tp_range.return_value = [
            {
                "workoutDay": "2026-03-12T00:00:00",
                "workoutId": 222,
                "title": "Coach Day 1",
                "workoutTypeValueId": 2,
                "structure": {"structure": [{"steps": [{"name": "Active", "length": {"unit": "second", "value": 1200}, "targets": [{"minValue": 55, "maxValue": 65}]}]}]},
            }
        ]

        horizon = build_coach_mode_horizon({}, "cycling", focus_sport="cycling", recent_activities=[], start_day="2026-03-12")
        self.assertTrue(horizon["coach_mode"])
        self.assertIn("coach_horizon_summary", horizon)
        self.assertEqual(horizon["days"][0]["plan_source"], "trainingpeaks")


if __name__ == "__main__":
    unittest.main()
