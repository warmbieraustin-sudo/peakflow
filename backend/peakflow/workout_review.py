from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import load_env, require_env
from .intervals import IntervalsClient

TP_BASE = "https://tp-api.trainingpeaks.com/v1"


@dataclass
class TrainingPeaksClient:
    token: str

    @classmethod
    def from_env(cls) -> "TrainingPeaksClient":
        load_env()
        return cls(token=require_env("TRAININGPEAKS_TOKEN"))

    def _get(self, path: str, params: Dict[str, Any] | None = None) -> Any:
        url = f"{TP_BASE}{path}"
        if params:
            url += f"?{urlencode(params)}"

        req = Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except HTTPError as exc:
            body = exc.read().decode(errors="ignore")
            raise RuntimeError(f"TrainingPeaks API HTTP {exc.code}: {body}") from exc
        except URLError as exc:
            raise RuntimeError(f"TrainingPeaks API connection error: {exc}") from exc

    def workouts_for_day(self, day: str) -> List[Dict[str, Any]]:
        out = self._get("/workouts", {"startDate": day, "endDate": day})
        if isinstance(out, list):
            return out
        return out.get("items", []) if isinstance(out, dict) else []


def _tp_workouts_via_script(day: str) -> List[Dict[str, Any]]:
    tp_script = Path.home() / ".openclaw" / "workspace" / "skills" / "trainingpeaks" / "scripts" / "tp.py"
    cmd = ["/opt/homebrew/bin/python3", str(tp_script), "workouts", day, day, "--json"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(f"tp.py failed: {r.stderr.strip()}")
    out = json.loads(r.stdout)
    if isinstance(out, list):
        return out
    if isinstance(out, dict):
        return out.get("workouts", [])
    raise RuntimeError(f"tp.py returned unexpected JSON type: {type(out).__name__}")


def _parse_tp_structure(tp_workout: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract TP intervals from nested structure.structure[].steps[] format."""
    structure_root = tp_workout.get("structure")
    if not structure_root or not isinstance(structure_root, dict):
        return []

    structure_items = structure_root.get("structure", [])
    intervals: List[Dict[str, Any]] = []

    for item in structure_items:
        steps = item.get("steps", [])
        for step in steps:
            length = step.get("length", {})
            duration_sec = length.get("value") if length.get("unit") == "second" else None
            target = (step.get("targets") or [{}])[0]
            intervals.append(
                {
                    "index": len(intervals),
                    "type": step.get("intensityClass") or "work",
                    "duration_sec": duration_sec,
                    # TP plans here are typically %FTP, not watts.
                    "target_type": "power_pct_ftp",
                    "target_low": target.get("minValue"),
                    "target_high": target.get("maxValue"),
                    "label": step.get("name"),
                }
            )
    return intervals


def _latest_activity(activities: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not activities:
        return None
    activities = sorted(activities, key=lambda a: a.get("start_date_local") or "")
    return activities[-1]


def _clamp01(v: float) -> float:
    if v < 0:
        return 0.0
    if v > 1:
        return 1.0
    return v


def _normalize_planned_duration(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        v = float(value)
    except Exception:
        return None
    # TP totalTimePlanned can be in hours for some payloads.
    if 0 < v <= 24:
        return v * 3600.0
    return v


def _normalize_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalized plan format for both TP and LLM-generated workouts.
    LLM expected interval schema supports target_type: power_watts|power_pct_ftp|hr_bpm|rpe.
    """
    intervals = plan.get("intervals") or []
    norm: List[Dict[str, Any]] = []
    for idx, i in enumerate(intervals):
        norm.append(
            {
                "index": i.get("index", idx),
                "type": i.get("type", "work"),
                "label": i.get("label") or f"interval_{idx+1}",
                "duration_sec": i.get("duration_sec"),
                "target_type": i.get("target_type", "power_pct_ftp"),
                "target_low": i.get("target_low"),
                "target_high": i.get("target_high"),
            }
        )
    return {
        "source": plan.get("source", "unknown"),
        "title": plan.get("title"),
        "planned_duration_sec": _normalize_planned_duration(plan.get("planned_duration_sec")),
        "planned_tss": plan.get("planned_tss"),
        "intervals": norm,
    }


def _choose_matching_tier(plan: Dict[str, Any], execution: Optional[Dict[str, Any]]) -> str:
    if not execution:
        return "none"
    has_hr = execution.get("avg_hr") is not None
    has_power = execution.get("weighted_avg_watts") is not None
    has_duration = execution.get("moving_time_sec") is not None

    plan_targets = {i.get("target_type") for i in plan.get("intervals", [])}
    if has_power and has_hr and ("power_watts" in plan_targets or "power_pct_ftp" in plan_targets):
        return "power_hr"
    if has_hr and ("hr_bpm" in plan_targets or "power_pct_ftp" in plan_targets or "rpe" in plan_targets):
        return "hr_only"
    if has_duration:
        return "duration_only"
    return "none"


def _duration_score(plan: Dict[str, Any], execution: Dict[str, Any]) -> float:
    planned = plan.get("planned_duration_sec")
    actual = execution.get("moving_time_sec")
    if not planned or not actual:
        return 0.5
    ratio = actual / float(planned)
    # Full score from 90%-110%, then taper.
    if 0.9 <= ratio <= 1.1:
        return 1.0
    return _clamp01(1.0 - abs(ratio - 1.0))


def _interval_compliance(plan: Dict[str, Any], execution: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Session-level fallback: compare interval targets against session metrics."""
    out: List[Dict[str, Any]] = []
    exec_watts = execution.get("weighted_avg_watts")
    exec_hr = execution.get("avg_hr")
    exec_intensity = execution.get("intensity")

    for i in plan.get("intervals", []):
        ttype = i.get("target_type")
        low = i.get("target_low")
        high = i.get("target_high") or low
        if low is None:
            continue

        executed = None
        delta = None
        hit = None

        if ttype == "power_watts" and exec_watts is not None:
            executed = exec_watts
            target_mid = (low + high) / 2.0
            delta = executed - target_mid
            hit = abs(delta) <= target_mid * 0.1
        elif ttype == "power_pct_ftp" and exec_intensity is not None:
            executed = exec_intensity
            target_mid = (low + high) / 2.0
            delta = executed - target_mid
            hit = abs(delta) <= 10.0
        elif ttype == "hr_bpm" and exec_hr is not None:
            executed = exec_hr
            target_mid = (low + high) / 2.0
            delta = executed - target_mid
            hit = abs(delta) <= 8.0

        if executed is not None:
            out.append(
                {
                    "label": i.get("label"),
                    "target_type": ttype,
                    "target_low": low,
                    "target_high": high,
                    "executed": round(float(executed), 1),
                    "delta": round(float(delta), 1) if delta is not None else None,
                    "hit": bool(hit),
                    "source": "session",
                }
            )

    return out


def _stream_map(streams: List[Dict[str, Any]]) -> Dict[str, List[Any]]:
    out: Dict[str, List[Any]] = {}
    for s in streams or []:
        st = s.get("type")
        if st:
            out[st] = s.get("data") or []
    return out


def _window_mean(values: List[Any], start_idx: int, end_idx: int) -> Optional[float]:
    window = [v for v in values[start_idx:end_idx] if isinstance(v, (int, float))]
    if not window:
        return None
    return sum(window) / float(len(window))


def _window_np_proxy(watts: List[Any], start_idx: int, end_idx: int) -> Optional[float]:
    window = [v for v in watts[start_idx:end_idx] if isinstance(v, (int, float))]
    if not window:
        return None
    return (sum((float(v) ** 4 for v in window)) / float(len(window))) ** 0.25


def _interval_compliance_streams(plan: Dict[str, Any], execution: Dict[str, Any], streams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    smap = _stream_map(streams)
    t = smap.get("time") or []
    watts = smap.get("watts") or []
    hr = smap.get("heartrate") or []
    if not t:
        return []

    # assume 1Hz arrays indexed by second; use cumulative planned durations for windows
    rows: List[Dict[str, Any]] = []
    cursor = 0
    ftp = execution.get("ftp")

    for i in plan.get("intervals", []):
        dur = i.get("duration_sec")
        if not isinstance(dur, (int, float)) or dur <= 0:
            continue
        start_idx = int(cursor)
        end_idx = int(cursor + dur)
        cursor = end_idx

        if start_idx >= len(t):
            break
        end_idx = min(end_idx, len(t))
        if end_idx <= start_idx:
            continue

        avg_w = _window_mean(watts, start_idx, end_idx) if watts else None
        np_proxy = _window_np_proxy(watts, start_idx, end_idx) if watts else None
        avg_hr = _window_mean(hr, start_idx, end_idx) if hr else None

        ttype = i.get("target_type")
        low = i.get("target_low")
        high = i.get("target_high") or low
        executed = None
        delta = None
        hit = None

        if low is not None:
            if ttype == "power_watts" and avg_w is not None:
                executed = avg_w
                target_mid = (low + high) / 2.0
                delta = executed - target_mid
                hit = abs(delta) <= target_mid * 0.1
            elif ttype == "power_pct_ftp" and avg_w is not None and ftp:
                executed = (avg_w / float(ftp)) * 100.0
                target_mid = (low + high) / 2.0
                delta = executed - target_mid
                hit = abs(delta) <= 10.0
            elif ttype == "hr_bpm" and avg_hr is not None:
                executed = avg_hr
                target_mid = (low + high) / 2.0
                delta = executed - target_mid
                hit = abs(delta) <= 8.0

        rows.append(
            {
                "label": i.get("label"),
                "target_type": ttype,
                "target_low": low,
                "target_high": high,
                "executed": round(float(executed), 1) if executed is not None else None,
                "delta": round(float(delta), 1) if delta is not None else None,
                "hit": bool(hit) if hit is not None else None,
                "avg_watts": round(float(avg_w), 1) if avg_w is not None else None,
                "np_proxy": round(float(np_proxy), 1) if np_proxy is not None else None,
                "avg_hr": round(float(avg_hr), 1) if avg_hr is not None else None,
                "window_start_sec": start_idx,
                "window_end_sec": end_idx,
                "source": "stream_window",
            }
        )

    return rows


def evaluate_plan_execution(plan: Dict[str, Any], execution_activity: Optional[Dict[str, Any]], streams: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    normalized = _normalize_plan(plan)
    reason_codes: List[str] = []

    if not execution_activity:
        return {
            "matching_tier": "none",
            "interval_matching": "not_available",
            "score": None,
            "confidence": "low",
            "reason_codes": ["NO_EXECUTION_ACTIVITY"],
            "intervals": [],
        }

    tier = _choose_matching_tier(normalized, execution_activity)
    duration = _duration_score(normalized, execution_activity)

    # Prefer stream-window interval matching when streams are present.
    interval_rows = _interval_compliance_streams(normalized, execution_activity, streams or [])
    if interval_rows:
        reason_codes.append("STREAM_WINDOW_MATCH")
    else:
        interval_rows = _interval_compliance(normalized, execution_activity)
        if interval_rows:
            reason_codes.append("SESSION_LEVEL_FALLBACK_MATCH")

    interval_hits = [r for r in interval_rows if r.get("hit") is not None]
    interval_score = None
    if interval_hits:
        hits = sum(1 for r in interval_hits if r.get("hit"))
        interval_score = hits / float(len(interval_hits))
    else:
        reason_codes.append("NO_COMPARABLE_INTERVAL_TARGETS")

    if tier == "power_hr":
        if interval_score is None:
            score = duration * 0.6
            confidence = "medium"
        else:
            score = 0.7 * interval_score + 0.3 * duration
            confidence = "high"
    elif tier == "hr_only":
        if interval_score is None:
            score = duration * 0.7
        else:
            score = 0.55 * interval_score + 0.45 * duration
        confidence = "medium"
        reason_codes.append("HR_OR_INTENSITY_FALLBACK")
    elif tier == "duration_only":
        score = duration
        confidence = "low"
        reason_codes.append("DURATION_ONLY_MATCH")
    else:
        score = duration * 0.5
        confidence = "low"
        reason_codes.append("INSUFFICIENT_EXECUTION_SIGNALS")

    score_100 = round(score * 100.0, 1)
    if score_100 >= 80:
        match_label = "matched"
    elif score_100 >= 50:
        match_label = "partial"
    else:
        match_label = "missed"

    return {
        "matching_tier": tier,
        "interval_matching": match_label,
        "score": score_100,
        "confidence": confidence,
        "reason_codes": reason_codes,
        "intervals": interval_rows,
    }


def build_latest_workout_review(day: str | None = None) -> Dict[str, Any]:
    target_day = day or date.today().isoformat()

    tp_data: Dict[str, Any] = {
        "source": "trainingpeaks",
        "day": target_day,
        "status": "unavailable",
        "workout_title": None,
        "intervals": [],
    }

    try:
        tp_workouts = _tp_workouts_via_script(target_day)
        if tp_workouts:
            w = tp_workouts[0]
            if not isinstance(w, dict):
                raise RuntimeError(f"tp.py returned non-object workout item: {type(w).__name__}")
            tp_data.update(
                {
                    "status": "ok",
                    "workout_title": w.get("title") or w.get("name"),
                    "intervals": _parse_tp_structure(w),
                    "planned_tss": w.get("plannedTss") or w.get("tssPlanned"),
                    "planned_duration_sec": _normalize_planned_duration(
                        w.get("plannedDurationSeconds") or w.get("durationSeconds") or w.get("totalTimePlanned")
                    ),
                }
            )
        else:
            tp_data["status"] = "empty"
    except Exception:
        tp_data["status"] = "unavailable"

    icu = IntervalsClient.from_env()
    activities = icu.activities(target_day, target_day)
    latest = _latest_activity(activities)

    execution = {
        "source": "intervals.icu",
        "status": "ok" if latest else "empty",
        "activity": None,
    }
    streams: List[Dict[str, Any]] = []

    if latest:
        execution["activity"] = {
            "id": latest.get("id"),
            "name": latest.get("name"),
            "start_date_local": latest.get("start_date_local"),
            "moving_time_sec": latest.get("moving_time"),
            "avg_watts": latest.get("average_watts"),
            "weighted_avg_watts": latest.get("icu_weighted_avg_watts"),
            "avg_hr": latest.get("average_heartrate"),
            "training_load": latest.get("icu_training_load"),
            "intensity": latest.get("icu_intensity"),
            "decoupling": latest.get("decoupling"),
            "calories": latest.get("calories"),
            "ftp": latest.get("icu_ftp") or latest.get("icu_pm_ftp_watts"),
        }
        try:
            streams = icu.activity_streams(str(latest.get("id")))
        except Exception:
            streams = []

    plan = {
        "source": "trainingpeaks",
        "title": tp_data.get("workout_title"),
        "planned_duration_sec": tp_data.get("planned_duration_sec"),
        "planned_tss": tp_data.get("planned_tss"),
        "intervals": tp_data.get("intervals", []),
    }
    analysis = evaluate_plan_execution(plan, execution.get("activity"), streams=streams)

    return {
        "date": target_day,
        "prescription": tp_data,
        "execution": execution,
        "analysis": {
            "prescription_available": tp_data.get("status") == "ok",
            "execution_available": execution.get("status") == "ok",
            "interval_matching": analysis.get("interval_matching", "not_available"),
            "matching_tier": analysis.get("matching_tier", "none"),
            "score": analysis.get("score"),
            "confidence": analysis.get("confidence", "low"),
            "reason_codes": analysis.get("reason_codes", []),
            "intervals": analysis.get("intervals", []),
        },
        "fallbacks": {
            "garmin_fallback_required": execution.get("status") != "ok",
        },
    }
