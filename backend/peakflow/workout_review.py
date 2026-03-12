from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import subprocess

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
        # conservative endpoint shape; if token/endpoint is unavailable in env, caller should fallback
        out = self._get("/workouts", {"startDate": day, "endDate": day})
        if isinstance(out, list):
            return out
        return out.get("items", []) if isinstance(out, dict) else []


def _tp_workouts_via_script(day: str) -> List[Dict[str, Any]]:
    """Preferred local TP path in this environment (cookie-auth script)."""
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
    """
    Extract interval targets from TP structured workout if present.
    Handles nested TP API format: structure.structure[].steps[]
    """
    structure_root = tp_workout.get("structure")
    if not structure_root or not isinstance(structure_root, dict):
        return []
    
    structure_items = structure_root.get("structure", [])
    intervals: List[Dict[str, Any]] = []
    
    for item_idx, item in enumerate(structure_items):
        steps = item.get("steps", [])
        for step_idx, step in enumerate(steps):
            length = step.get("length", {})
            duration_sec = length.get("value") if length.get("unit") == "second" else None
            
            targets = step.get("targets", [{}])
            target = targets[0] if targets else {}
            
            intervals.append({
                "index": len(intervals),
                "type": step.get("intensityClass") or "work",
                "duration_sec": duration_sec,
                "target_power_low": target.get("minValue"),
                "target_power_high": target.get("maxValue"),
                "label": step.get("name"),
            })
    
    return intervals


def _latest_activity(activities: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not activities:
        return None
    activities = sorted(activities, key=lambda a: a.get("start_date_local") or "")
    return activities[-1]


def _match_intervals(tp_intervals: List[Dict[str, Any]], execution_activity: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    First-pass interval matching between TP prescription and ICU execution.
    Returns analysis with match status and per-interval deltas.
    """
    if not tp_intervals or not execution_activity:
        return {"status": "not_available", "intervals": []}
    
    # For now, just flag key work intervals and compare to execution metrics
    work_intervals = [i for i in tp_intervals if i.get("type") in ["work", "active"]]
    
    if not work_intervals:
        return {"status": "no_work_intervals", "intervals": []}
    
    # Simple first-pass: compare planned power targets to execution avg/weighted
    exec_avg = execution_activity.get("avg_watts")
    exec_weighted = execution_activity.get("weighted_avg_watts")
    
    intervals_analysis = []
    for interval in work_intervals:
        target_low = interval.get("target_power_low")
        target_high = interval.get("target_power_high")
        
        if target_low and exec_weighted:
            # Compare to weighted avg (closer to NP)
            target_mid = (target_low + (target_high or target_low)) / 2
            delta = exec_weighted - target_mid
            hit = abs(delta) <= (target_mid * 0.1)  # within 10%
            
            intervals_analysis.append({
                "label": interval.get("label"),
                "target_range": f"{target_low}-{target_high or target_low}%",
                "executed_watts": exec_weighted,
                "delta_watts": round(delta, 1),
                "hit": hit,
            })
    
    overall_status = "matched" if intervals_analysis else "pending"
    
    return {
        "status": overall_status,
        "intervals": intervals_analysis,
    }


def build_latest_workout_review(day: str | None = None) -> Dict[str, Any]:
    target_day = day or date.today().isoformat()

    # 1) Prescription source first (TP)
    tp_data: Dict[str, Any] = {
        "source": "trainingpeaks",
        "day": target_day,
        "status": "unavailable",
        "workout_title": None,
        "intervals": [],
    }

    tp_available = False
    try:
        # Preferred in this workspace: tp.py script (cookie auth)
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
                    "planned_duration_sec": w.get("plannedDurationSeconds") or w.get("durationSeconds") or w.get("totalTimePlanned"),
                }
            )
            tp_available = True
        else:
            tp_data["status"] = "empty"
    except Exception:
        # Silent fallback - TP unavailable is expected in many environments
        tp_data["status"] = "unavailable"

    # 2) Execution source (Intervals)
    icu = IntervalsClient.from_env()
    activities = icu.activities(target_day, target_day)
    latest = _latest_activity(activities)

    execution = {
        "source": "intervals.icu",
        "status": "ok" if latest else "empty",
        "activity": None,
    }

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
        }

    # 3) Interval matching analysis
    interval_analysis = _match_intervals(tp_data.get("intervals", []), execution.get("activity"))
    
    # 4) Review contract
    review = {
        "date": target_day,
        "prescription": tp_data,
        "execution": execution,
        "analysis": {
            "prescription_available": tp_data.get("status") == "ok",
            "execution_available": execution.get("status") == "ok",
            "interval_matching": interval_analysis.get("status", "not_available"),
            "intervals": interval_analysis.get("intervals", []),
        },
        "fallbacks": {
            "garmin_fallback_required": execution.get("status") != "ok",
        },
    }

    return review
