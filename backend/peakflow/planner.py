from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Tuple

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

ALLOWED_TARGET_TYPES = {"power_watts", "power_pct_ftp", "hr_bpm", "pace", "rpe", "load", "duration"}


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
                {
                    "label": "main_sets",
                    "duration_sec": 3000,
                    "target_type": "rpe",
                    "target_low": 6 if intensity != "easy" else 5,
                    "target_high": 8 if intensity == "hard" else 7,
                },
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


def validate_plan_schema(plan: Dict[str, Any]) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    if not isinstance(plan, dict):
        return False, ["PLAN_NOT_OBJECT"]

    sport = plan.get("sport_type")
    if sport not in SUPPORTED_SPORTS:
        reasons.append("INVALID_SPORT_TYPE")

    title = plan.get("title")
    if not isinstance(title, str) or not title.strip():
        reasons.append("MISSING_TITLE")

    blocks = plan.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        reasons.append("MISSING_BLOCKS")
        return False, reasons

    for idx, b in enumerate(blocks):
        if not isinstance(b, dict):
            reasons.append(f"BLOCK_{idx}_NOT_OBJECT")
            continue

        if not b.get("label"):
            reasons.append(f"BLOCK_{idx}_MISSING_LABEL")

        dur = b.get("duration_sec")
        if not isinstance(dur, (int, float)) or dur <= 0:
            reasons.append(f"BLOCK_{idx}_INVALID_DURATION")

        ttype = b.get("target_type")
        if ttype not in ALLOWED_TARGET_TYPES:
            reasons.append(f"BLOCK_{idx}_INVALID_TARGET_TYPE")

        low = b.get("target_low")
        high = b.get("target_high")
        if low is not None and high is not None and isinstance(low, (int, float)) and isinstance(high, (int, float)) and low > high:
            reasons.append(f"BLOCK_{idx}_TARGET_RANGE_INVALID")

    return len(reasons) == 0, reasons


def _fallback_plan(selected_sport: str) -> Dict[str, Any]:
    return {
        "schema_version": "v1-modality-agnostic",
        "sport_type": selected_sport,
        "title": f"{selected_sport.title()} Easy Recovery",
        "blocks": [
            {"label": "easy", "duration_sec": 1800, "target_type": "rpe", "target_low": 2, "target_high": 4},
        ],
    }


def _apply_feedback_adjustments(
    selected_sport: str,
    athlete_mode: str,
    intensity: str,
    last_review: Dict[str, Any] | None,
) -> Dict[str, Any]:
    if not last_review:
        return {
            "intensity_band": intensity,
            "next_action": "follow_recommendation",
            "modification_reason": "no_recent_feedback",
            "feedback_used": False,
        }

    analysis = (last_review.get("analysis") or {})
    score = analysis.get("score")
    confidence = (analysis.get("confidence") or "low").lower()
    reasons = analysis.get("reason_codes") or []

    new_intensity = intensity
    next_action = "follow_recommendation"
    modification_reason = "feedback_neutral"

    if score is None:
        next_action = "collect_execution_data"
        modification_reason = "missing_score"
    elif score < 50 or confidence == "low":
        new_intensity = "easy"
        next_action = "reduce_load_and_focus_recovery"
        modification_reason = "low_score_or_low_confidence"
    elif score >= 85 and confidence in ("high", "medium") and intensity != "hard":
        new_intensity = "moderate"
        next_action = "progress_gradually"
        modification_reason = "strong_recent_execution"

    if "NO_EXECUTION_ACTIVITY" in reasons:
        next_action = "confirm_completion_or_adjust_schedule"
        modification_reason = "no_recent_completed_workout"

    # Single-sport protection: keep quality work progression centered on focus sport day.
    if athlete_mode == "single_sport" and selected_sport == "cycling" and new_intensity == "easy" and score is not None and score >= 70:
        new_intensity = "moderate"
        modification_reason = "single_sport_progression_protection"

    return {
        "intensity_band": new_intensity,
        "next_action": next_action,
        "modification_reason": modification_reason,
        "feedback_used": True,
    }


def build_daily_recommendation(
    shell_payload: Dict[str, Any] | None,
    selected_sport: str,
    focus_sport: str | None = None,
    last_review: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    sport = (selected_sport or "cycling").strip().lower()
    if sport not in SUPPORTED_SPORTS:
        sport = "cycling"

    focus = (focus_sport or "").strip().lower() or None

    morning = ((shell_payload or {}).get("screens") or {}).get("morning_brief") or {}
    headline = morning.get("headline") or {}
    quick_load = morning.get("quick_load") or {}

    fresh = bool(headline.get("fresh", True))
    daily_load = quick_load.get("daily_training_load")
    base_intensity = _pick_intensity_band(fresh, daily_load)

    athlete_mode = "single_sport" if focus and focus == sport else "multi_sport"
    adjustment = _apply_feedback_adjustments(sport, athlete_mode, base_intensity, last_review)
    intensity = adjustment["intensity_band"]

    template = _templates_for_sport(sport, intensity)

    plan = {
        "schema_version": "v1-modality-agnostic",
        "sport_type": sport,
        "title": template["title"],
        "blocks": template["blocks"],
    }

    valid, reject_reasons = validate_plan_schema(plan)
    fallback_plan = None
    if not valid:
        fallback_plan = _fallback_plan(sport)

    return {
        "selected_sport": sport,
        "athlete_mode": athlete_mode,
        "intensity_band": intensity,
        "why": {
            "fresh": fresh,
            "daily_training_load": daily_load,
            "focus_sport": focus,
        },
        "plan": plan if valid else fallback_plan,
        "plan_validation": {
            "valid": valid,
            "reject_reasons": reject_reasons,
        },
        "next_action": adjustment["next_action"],
        "modification_reason": adjustment["modification_reason"],
        "fallback_plan": fallback_plan,
        "feedback_summary": {
            "used": adjustment["feedback_used"],
            "review_score": ((last_review or {}).get("analysis") or {}).get("score"),
            "review_confidence": ((last_review or {}).get("analysis") or {}).get("confidence"),
        },
    }


def summarize_recent_load(activities: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = sorted(activities or [], key=lambda a: a.get("start_date_local") or "")
    loads = [float(a.get("icu_training_load") or 0.0) for a in rows]
    intensities = [float(a.get("icu_intensity") or 0.0) for a in rows]

    last7 = loads[-7:] if len(loads) >= 7 else loads
    prev21 = loads[-28:-7] if len(loads) >= 28 else loads[:-7]

    last7_total = sum(last7)
    prev21_weekly_avg = (sum(prev21) / 3.0) if prev21 else (sum(loads) / max(1, len(loads) / 7.0))

    hard_sessions_last7 = sum(1 for i in (intensities[-7:] if intensities else []) if i >= 80)
    return {
        "days_considered": len(rows),
        "last7_load": round(last7_total, 1),
        "prev21_weekly_avg_load": round(prev21_weekly_avg, 1),
        "hard_sessions_last7": hard_sessions_last7,
    }


def decide_phase(summary: Dict[str, Any], fresh: bool = True) -> Dict[str, Any]:
    last7 = float(summary.get("last7_load") or 0.0)
    prev_avg = float(summary.get("prev21_weekly_avg_load") or 0.0)
    hard = int(summary.get("hard_sessions_last7") or 0)

    deload_trigger = (prev_avg > 0 and last7 > prev_avg * 1.25) or hard >= 4 or (not fresh and last7 > 0)
    if deload_trigger:
        return {
            "phase": "deload",
            "reason": "high_recent_load_or_fatigue",
            "polarization_target": {"easy": 0.9, "hard": 0.1},
        }

    if prev_avg > 0 and last7 < prev_avg * 0.75:
        return {
            "phase": "rebuild",
            "reason": "underload_recent_block",
            "polarization_target": {"easy": 0.8, "hard": 0.2},
        }

    return {
        "phase": "build",
        "reason": "normal_progression",
        "polarization_target": {"easy": 0.8, "hard": 0.2},
    }


def _weekly_intensity_pattern(phase: str) -> List[str]:
    if phase == "deload":
        return ["easy", "easy", "easy", "rest", "easy", "moderate", "rest"]
    if phase == "rebuild":
        return ["moderate", "easy", "hard", "easy", "moderate", "hard", "rest"]
    return ["moderate", "easy", "hard", "easy", "moderate", "hard", "easy"]


def build_horizon_plan(
    shell_payload: Dict[str, Any] | None,
    selected_sport: str,
    focus_sport: str | None = None,
    recent_activities: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    sport = (selected_sport or "cycling").strip().lower()
    if sport not in SUPPORTED_SPORTS:
        sport = "cycling"

    morning = ((shell_payload or {}).get("screens") or {}).get("morning_brief") or {}
    fresh = bool((morning.get("headline") or {}).get("fresh", True))

    summary = summarize_recent_load(recent_activities or [])
    phase = decide_phase(summary, fresh=fresh)
    pattern = _weekly_intensity_pattern(phase["phase"])

    start = date.today()
    days: List[Dict[str, Any]] = []
    for i in range(28):
        d = start + timedelta(days=i)
        intensity = pattern[i % 7]
        # honor explicit activity selection on day0; default to focus sport cadence later
        day_sport = sport if i == 0 else (focus_sport or sport)

        if intensity == "rest":
            plan = {
                "schema_version": "v1-modality-agnostic",
                "sport_type": day_sport,
                "title": "Recovery / Rest",
                "blocks": [{"label": "recovery", "duration_sec": 1200, "target_type": "rpe", "target_low": 1, "target_high": 2}],
            }
        else:
            t = _templates_for_sport(day_sport, "easy" if intensity == "rest" else intensity)
            plan = {
                "schema_version": "v1-modality-agnostic",
                "sport_type": day_sport,
                "title": t["title"],
                "blocks": t["blocks"],
            }

        days.append(
            {
                "date": d.isoformat(),
                "firm": i < 7,
                "sport_type": day_sport,
                "intensity_band": intensity,
                "plan": plan,
            }
        )

    return {
        "selected_sport": sport,
        "focus_sport": focus_sport,
        "horizon": {"firm_days": 7, "soft_days": 28},
        "periodization": {
            "phase": phase["phase"],
            "reason": phase["reason"],
            "polarization_target": phase["polarization_target"],
            "recent_load_summary": summary,
        },
        "days": days,
    }
