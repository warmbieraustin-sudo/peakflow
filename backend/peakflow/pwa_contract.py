from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .query import build_consumer_contract


def build_alpha_shell_payload(base_dir: Path, day: str | None = None) -> Dict[str, Any] | None:
    """
    Minimal payload contract for PeakFlow alpha PWA shell.

    Screen targets:
      1) Morning Brief
      2) Recovery + Load
      3) Chat Context
    """
    contract = build_consumer_contract(base_dir, day=day)
    if not contract:
        return None

    recovery = contract.get("recovery", {})
    load = contract.get("load", {})
    summary = contract.get("activity_summary", {})

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": contract["date"],
        "fresh": contract.get("fresh"),
        "freshness_age_minutes": contract.get("freshness_age_minutes"),
        "screens": {
            "morning_brief": {
                "headline": {
                    "fresh": contract.get("fresh"),
                    "freshness_age_minutes": contract.get("freshness_age_minutes"),
                },
                "quick_recovery": {
                    "weight_kg": recovery.get("weight_kg"),
                    "resting_hr": recovery.get("resting_hr"),
                    "hrv": recovery.get("hrv"),
                    "sleep_score": recovery.get("sleep_score"),
                },
                "quick_load": {
                    "ctl": load.get("ctl"),
                    "atl": load.get("atl"),
                    "daily_training_load": load.get("daily_training_load"),
                },
            },
            "recovery_load": {
                "recovery": recovery,
                "load": load,
                "activity_summary": summary,
            },
            "chat_context": {
                "date": contract["date"],
                "fresh": contract.get("fresh"),
                "recovery": recovery,
                "load": load,
                "activity_summary": summary,
                "activity_count": contract.get("activity_count", 0),
            },
        },
    }
