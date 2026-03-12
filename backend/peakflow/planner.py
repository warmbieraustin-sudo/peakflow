from __future__ import annotations

from typing import Any, Dict, List

SUPPORTED_SPORTS: List[str] = [
    "cycling",
    "running",
    "hiking",
    "skiing",
    "strength",
    "yoga",
    "swimming",
    "walking",
]


def _pick_intensity_band(fresh: bool, load: float | None) -> str:
    if not fresh:
        return "easy"
    if load is None:
        return "moderate"
    if load > 80:
        return "easy"
    if load < 30:
        return "hard"
    return "moderate"


def _templates_for_sport(sport: str, intensity: str) -> Dict[str, Any]:
    # Minimal v1 templates; these become the universal plan schema for LLM + rules.
    if sport == "cycling":
        if intensity == "hard":
            return {
                "title": "Bike Threshold Intervals",
                "blocks": [
                    {"label": "warmup", "duration_sec": 900, "target_type": "power_pct_ftp", "target_low": 55, "target_high": 65},
                    {"label": "work", "duration_sec": 4 * 480, "target_type": "power_pct_ftp", "target_low": 92, "target_high": 98},
                    {"label": "cooldown", "duration_sec": 600, "target_type": "power_pct_ftp", "target_low": 50, "target_high": 60},
                ],
            }
        if intensity == "easy":
            return {
                "title": "Bike Recovery Ride",
                "blocks": [
                    {"label": "easy", "duration_sec": 3600, "target_type": "power_pct_ftp", "target_low": 40, "target_high": 55},
                ],
            }
        return {
            "title": "Bike Endurance",
            "blocks": [
                {"label": "endurance", "duration_sec": 5400, "target_type": "power_pct_ftp", "target_low": 60, "target_high": 72},
            ],
        }

    if sport == "running":
        if intensity == "hard":
            return {
                "title": "Run Tempo Intervals",
                "blocks": [
                    {"label": "warmup", "duration_sec": 900, "target_type": "rpe", "target_low": 3, "target_high": 4},
                    {"label": "tempo", "duration_sec": 3 * 600, "target_type": "rpe", "target_low": 7, "target_high": 8},
                    {"label": "cooldown", "duration_sec": 600, "target_type": "rpe", "target_low": 2, "target_high": 3},
                ],
            }
        return {
            "title": "Run Aerobic",
            "blocks": [
                {"label": "steady", "duration_sec": 2700, "target_type": "rpe", "target_low": 4, "target_high": 5},
            ],
        }

    if sport == "strength":
        return {
            "title": "Strength Session",
            "blocks": [
                {"label": "main_sets", "duration_sec": 3000, "target_type": "rpe", "target_low": 6 if intensity != "easy" else 5, "target_high": 8 if intensity == "hard" else 7},
            ],
        }

    if sport == "yoga":
        return {
            "title": "Mobility + Recovery Yoga",
            "blocks": [
                {"label": "flow", "duration_sec": 1800, "target_type": "rpe", "target_low": 2, "target_high": 4},
            ],
        }

    # default template for mixed/outdoor modalities (hiking/skiing/swimming/walking)
    return {
        "title": f"{sport.title()} Aerobic Session",
        "blocks": [
            {"label": "steady", "duration_sec": 3600, "target_type": "rpe", "target_low": 4, "target_high": 6},
        ],
    }


def build_daily_recommendation(
    shell_payload: Dict[str, Any] | None,
    selected_sport: str,
    focus_sport: str | None = None,
) -> Dict[str, Any]:
    sport = (selected_sport or "cycling").strip().lower()
    if sport not in SUPPORTED_SPORTS:
        sport = "cycling"

    morning = ((shell_payload or {}).get("screens") or {}).get("morning_brief") or {}
    headline = morning.get("headline") or {}
    quick_load = morning.get("quick_load") or {}

    fresh = bool(headline.get("fresh", True))
    daily_load = quick_load.get("daily_training_load")
    intensity = _pick_intensity_band(fresh, daily_load)

    template = _templates_for_sport(sport, intensity)

    athlete_mode = "single_sport" if focus_sport and focus_sport.strip().lower() == sport else "multi_sport"

    return {
        "selected_sport": sport,
        "athlete_mode": athlete_mode,
        "intensity_band": intensity,
        "why": {
            "fresh": fresh,
            "daily_training_load": daily_load,
            "focus_sport": focus_sport,
        },
        "plan": {
            "schema_version": "v1-modality-agnostic",
            "sport_type": sport,
            "title": template["title"],
            "blocks": template["blocks"],
        },
    }
