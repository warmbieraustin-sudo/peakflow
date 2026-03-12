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
    Keeps schema generic so we can map richer fields later.
    """
    structure = tp_workout.get("structure") or []
    intervals: List[Dict[str, Any]] = []
    for idx, step in enumerate(structure):
        intervals.append(
            {
                "index": idx,
                "type": step.get("type"),
                "duration_sec": step.get("durationSeconds") or step.get("seconds"),
                "target_power_low": step.get("targetPowerLow"),
                "target_power_high": step.get("targetPowerHigh"),
                "label": step.get("name") or step.get("label"),
            }
        )
    return intervals


def _latest_activity(activities: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not activities:
        return None
    activities = sorted(activities, key=lambda a: a.get("start_date_local") or "")
    return activities[-1]


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

    tp_error = None
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
        else:
            tp_data["status"] = "empty"
    except Exception as e:
        tp_error = str(e)
        # Optional fallback if direct API token exists
        try:
            tp = TrainingPeaksClient.from_env()
            tp_workouts = tp.workouts_for_day(target_day)
            if tp_workouts:
                w = tp_workouts[0]
                if not isinstance(w, dict):
                    raise RuntimeError(f"tp api returned non-object workout item: {type(w).__name__}")
                tp_data.update(
                    {
                        "status": "ok",
                        "workout_title": w.get("title") or w.get("name"),
                        "intervals": _parse_tp_structure(w),
                        "planned_tss": w.get("plannedTss") or w.get("tssPlanned"),
                        "planned_duration_sec": w.get("plannedDurationSeconds") or w.get("durationSeconds"),
                    }
                )
            else:
                tp_data["status"] = "empty"
        except Exception as e2:
            tp_error = f"{tp_error} | api_fallback: {e2}"

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

    # 3) Review contract
    review = {
        "date": target_day,
        "prescription": tp_data,
        "execution": execution,
        "analysis": {
            "prescription_available": tp_data.get("status") == "ok",
            "execution_available": execution.get("status") == "ok",
            "interval_matching": "pending" if tp_data.get("status") == "ok" and execution.get("status") == "ok" else "not_available",
        },
        "fallbacks": {
            "garmin_fallback_required": execution.get("status") != "ok",
            "tp_error": tp_error,
        },
    }

    return review
