#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from peakflow.pwa_contract import build_alpha_shell_payload
from peakflow.workout_review import build_latest_workout_review
from peakflow.intervals import IntervalsClient
from peakflow.planner import (
    SUPPORTED_SPORTS,
    build_coach_mode_horizon,
    build_coach_mode_recommendation,
    build_daily_recommendation,
    build_horizon_plan,
)
from peakflow.llm_client import LLMClient

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT.parent / "frontend"
SILVER_DIR = ROOT / "data" / "silver"
ALPHA_TOKEN = os.environ.get("PEAKFLOW_ALPHA_TOKEN", "").strip()

DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PLANNER_STATE_PATH = ROOT / "data" / "app-state" / "planner_state.json"
PLANNER_FEEDBACK_LOG = ROOT / "data" / "app-state" / "reco_feedback.jsonl"
FEEDBACK_SCHEMA_VERSION = "v1"
MAX_FEEDBACK_ROWS = int(os.environ.get("PEAKFLOW_MAX_FEEDBACK_ROWS", "5000"))


def _load_planner_state() -> dict:
    if not PLANNER_STATE_PATH.exists():
        return {"athletes": {}}
    try:
        return json.loads(PLANNER_STATE_PATH.read_text())
    except Exception:
        return {"athletes": {}}


def _save_planner_state(state: dict) -> None:
    PLANNER_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLANNER_STATE_PATH.write_text(json.dumps(state, indent=2))


def _get_athlete_state(athlete_id: str) -> dict:
    state = _load_planner_state()
    return (state.get("athletes") or {}).get(athlete_id, {})


def _upsert_athlete_state(athlete_id: str, updates: dict) -> dict:
    state = _load_planner_state()
    athletes = state.setdefault("athletes", {})
    row = athletes.setdefault(athlete_id, {})
    row.update({k: v for k, v in updates.items() if v is not None})
    _save_planner_state(state)
    return row


def _prune_feedback_log() -> None:
    if not PLANNER_FEEDBACK_LOG.exists():
        return
    lines = PLANNER_FEEDBACK_LOG.read_text().splitlines()
    if len(lines) <= MAX_FEEDBACK_ROWS:
        return
    kept = lines[-MAX_FEEDBACK_ROWS:]
    PLANNER_FEEDBACK_LOG.write_text("\n".join(kept) + "\n")


def _append_feedback_row(row: dict) -> None:
    PLANNER_FEEDBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
    with PLANNER_FEEDBACK_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    _prune_feedback_log()


def _feedback_summary() -> dict:
    if not PLANNER_FEEDBACK_LOG.exists():
        return {"count": 0, "avg_relevance": None, "schema_version": FEEDBACK_SCHEMA_VERSION}
    rows = []
    for line in PLANNER_FEEDBACK_LOG.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    rel = [r.get("relevance") for r in rows if isinstance(r.get("relevance"), (int, float))]
    perceived = {}
    for r in rows:
        p = r.get("perceived")
        if not p:
            continue
        perceived[p] = perceived.get(p, 0) + 1
    return {
        "count": len(rows),
        "avg_relevance": round(sum(rel) / len(rel), 2) if rel else None,
        "schema_version": FEEDBACK_SCHEMA_VERSION,
        "max_rows": MAX_FEEDBACK_ROWS,
        "perceived_counts": perceived,
    }


def _json(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
    handler.end_headers()
    handler.wfile.write(body)


def _text(handler: BaseHTTPRequestHandler, status: int, text: str, content_type: str = "text/plain") -> None:
    body = text.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class AlphaHandler(BaseHTTPRequestHandler):
    def _auth_ok(self) -> bool:
        if not ALPHA_TOKEN:
            return True

        hdr = self.headers.get("Authorization", "")
        token = ""
        if hdr.startswith("Bearer "):
            token = hdr.replace("Bearer ", "", 1).strip()

        if not token:
            q = parse_qs(urlparse(self.path).query)
            token = (q.get("token") or [""])[0].strip()

        return token == ALPHA_TOKEN

    def _serve_frontend(self, path: str) -> bool:
        rel = "index.html" if path == "/" else path.lstrip("/")
        target = (FRONTEND_DIR / rel).resolve()
        if not str(target).startswith(str(FRONTEND_DIR.resolve())):
            return False
        if not target.exists() or not target.is_file():
            return False

        content_type = "text/plain"
        if target.suffix == ".html":
            content_type = "text/html"
        elif target.suffix == ".js":
            content_type = "application/javascript"
        elif target.suffix == ".css":
            content_type = "text/css"

        _text(self, HTTPStatus.OK, target.read_text(), content_type=content_type)
        return True

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            if not self._auth_ok():
                return _json(self, HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})

            if path == "/api/health":
                return _json(self, HTTPStatus.OK, {"ok": True, "service": "peakflow-alpha-api"})

            if path == "/api/alpha/routes":
                return _json(
                    self,
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "routes": [
                            {"path": "/", "screen": "morning_brief"},
                            {"path": "/recovery", "screen": "recovery_load"},
                            {"path": "/chat", "screen": "chat_context"},
                            {"path": "/plan", "screen": "daily_plan"},
                        ],
                        "api": [
                            "/api/health",
                            "/api/alpha/shell/today",
                            "/api/alpha/shell/YYYY-MM-DD",
                            "/api/alpha/workout/latest",
                            "/api/alpha/planner/modalities",
                            "/api/alpha/planner/state?athleteId=default",
                            "/api/alpha/planner/feedback/log?athleteId=default&relevance=4",
                            "/api/alpha/planner/feedback/summary",
                            "/api/alpha/planner/recommendation?sport=cycling",
                            "/api/alpha/planner/recommendation?sport=cycling&coachMode=true",
                            "/api/alpha/planner/horizon?sport=cycling&focusSport=cycling",
                            "/api/alpha/llm/debrief/today",
                        ],
                    },
                )

            if path == "/api/alpha/shell/today":
                payload = build_alpha_shell_payload(SILVER_DIR, day=None)
                if not payload:
                    return _json(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "no_data"})
                return _json(self, HTTPStatus.OK, {"ok": True, "payload": payload})

            if path.startswith("/api/alpha/shell/"):
                day = path.rsplit("/", 1)[-1]
                if not DAY_RE.match(day):
                    return _json(self, HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_day"})
                payload = build_alpha_shell_payload(SILVER_DIR, day=day)
                if not payload:
                    return _json(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "no_data_for_day"})
                return _json(self, HTTPStatus.OK, {"ok": True, "payload": payload})

            if path == "/api/alpha/workout/latest":
                q = parse_qs(parsed.query)
                day = (q.get("day") or [None])[0]
                payload = build_latest_workout_review(day=day)
                return _json(self, HTTPStatus.OK, {"ok": True, "payload": payload})

            if path == "/api/alpha/planner/modalities":
                return _json(self, HTTPStatus.OK, {"ok": True, "modalities": SUPPORTED_SPORTS})

            if path == "/api/alpha/planner/state":
                q = parse_qs(parsed.query)
                athlete_id = (q.get("athleteId") or ["default"])[0]
                return _json(self, HTTPStatus.OK, {"ok": True, "athlete_id": athlete_id, "state": _get_athlete_state(athlete_id)})

            if path == "/api/alpha/planner/feedback/log":
                q = parse_qs(parsed.query)
                athlete_id = (q.get("athleteId") or ["default"])[0]
                relevance_raw = (q.get("relevance") or [None])[0]
                perceived = (q.get("perceived") or [None])[0]
                rec_id = (q.get("recId") or [None])[0]
                note = (q.get("note") or [None])[0]

                relevance = None
                if relevance_raw is not None:
                    try:
                        relevance = int(relevance_raw)
                    except Exception:
                        relevance = None

                row = {
                    "schema_version": FEEDBACK_SCHEMA_VERSION,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "athlete_id": athlete_id,
                    "relevance": relevance,
                    "perceived": perceived,
                    "rec_id": rec_id,
                    "note": note,
                }
                _append_feedback_row(row)
                return _json(self, HTTPStatus.OK, {"ok": True, "logged": True, "row": row})

            if path == "/api/alpha/planner/feedback/summary":
                return _json(self, HTTPStatus.OK, {"ok": True, "summary": _feedback_summary()})

            if path == "/api/alpha/planner/recommendation":
                q = parse_qs(parsed.query)
                day = (q.get("day") or [None])[0]
                athlete_id = (q.get("athleteId") or ["default"])[0]
                sport_q = (q.get("sport") or [None])[0]
                focus_q = (q.get("focusSport") or [None])[0]
                feedback_day = (q.get("feedbackDay") or [None])[0]
                athlete_feedback_q = (q.get("athleteFeedback") or [None])[0]
                coach_mode_q = (q.get("coachMode") or [None])[0]

                saved = _get_athlete_state(athlete_id)
                sport = sport_q or saved.get("selected_sport") or "cycling"
                focus_sport = focus_q or saved.get("focus_sport")
                athlete_feedback = athlete_feedback_q or saved.get("athlete_feedback")
                coach_mode = (
                    ((coach_mode_q or "").strip().lower() in ("1", "true", "yes", "on"))
                    if coach_mode_q is not None
                    else bool(saved.get("coach_mode", False))
                )

                if not feedback_day:
                    feedback_day = (date.today() - timedelta(days=1)).isoformat()

                _upsert_athlete_state(
                    athlete_id,
                    {
                        "selected_sport": sport,
                        "focus_sport": focus_sport,
                        "athlete_feedback": athlete_feedback,
                        "coach_mode": coach_mode,
                    },
                )

                shell = build_alpha_shell_payload(SILVER_DIR, day=day)
                review = build_latest_workout_review(day=feedback_day)
                if coach_mode:
                    payload = build_coach_mode_recommendation(
                        shell,
                        sport,
                        focus_sport=focus_sport,
                        last_review=review,
                        athlete_feedback=athlete_feedback,
                        day=day,
                    )
                else:
                    payload = build_daily_recommendation(
                        shell,
                        sport,
                        focus_sport=focus_sport,
                        last_review=review,
                        athlete_feedback=athlete_feedback,
                    )
                payload["athlete_id"] = athlete_id
                return _json(self, HTTPStatus.OK, {"ok": True, "payload": payload})

            if path == "/api/alpha/planner/horizon":
                q = parse_qs(parsed.query)
                day = (q.get("day") or [None])[0]
                athlete_id = (q.get("athleteId") or ["default"])[0]
                saved = _get_athlete_state(athlete_id)
                sport = (q.get("sport") or [saved.get("selected_sport") or "cycling"])[0]
                focus_sport = (q.get("focusSport") or [saved.get("focus_sport")])[0]
                coach_mode_q = (q.get("coachMode") or [None])[0]
                coach_mode = (
                    ((coach_mode_q or "").strip().lower() in ("1", "true", "yes", "on"))
                    if coach_mode_q is not None
                    else bool(saved.get("coach_mode", False))
                )

                shell = build_alpha_shell_payload(SILVER_DIR, day=day)
                icu = IntervalsClient.from_env()
                newest = date.today().isoformat()
                oldest = (date.today() - timedelta(days=35)).isoformat()
                recent_activities = icu.activities(oldest, newest)

                if coach_mode:
                    payload = build_coach_mode_horizon(shell, sport, focus_sport=focus_sport, recent_activities=recent_activities, start_day=day)
                else:
                    payload = build_horizon_plan(shell, sport, focus_sport=focus_sport, recent_activities=recent_activities)
                payload["athlete_id"] = athlete_id
                return _json(self, HTTPStatus.OK, {"ok": True, "payload": payload})

            if path == "/api/alpha/llm/debrief/today":
                try:
                    # Get today's shell payload for recovery data
                    shell = build_alpha_shell_payload(SILVER_DIR, day=None)
                    if not shell:
                        return _json(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "no_recovery_data"})
                    
                    # Get yesterday's workout review
                    yesterday = (date.today() - timedelta(days=1)).isoformat()
                    yesterday_workout = build_latest_workout_review(day=yesterday)
                    
                    # Extract recovery and load data
                    recovery_raw = shell.get("screens", {}).get("recovery_load", {}).get("recovery", {})
                    load_raw = shell.get("screens", {}).get("recovery_load", {}).get("load", {})
                    
                    # Initialize LLM client
                    llm = LLMClient()
                    
                    # Generate debrief
                    debrief = llm.generate_debrief(
                        recovery=recovery_raw,
                        yesterday_workout=yesterday_workout,
                        load=load_raw
                    )
                    
                    return _json(self, HTTPStatus.OK, {
                        "ok": True,
                        "debrief": debrief.model_dump(),
                        "cached": False
                    })
                    
                except Exception as e:
                    return _json(self, HTTPStatus.INTERNAL_SERVER_ERROR, {
                        "ok": False,
                        "error": "llm_generation_failed",
                        "detail": str(e)
                    })

            return _json(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})

        # Frontend static routes
        if self._serve_frontend(path):
            return

        # Simple SPA fallback
        if path in ["/recovery", "/chat", "/workout", "/plan"] and self._serve_frontend("/"):
            return

        return _text(self, HTTPStatus.NOT_FOUND, "Not found")


def main() -> None:
    host = os.environ.get("PEAKFLOW_API_HOST", "127.0.0.1")
    port = int(os.environ.get("PEAKFLOW_API_PORT", "8787"))

    server = ThreadingHTTPServer((host, port), AlphaHandler)
    print(f"PeakFlow alpha API listening on http://{host}:{port}")
    if ALPHA_TOKEN:
        print("Auth: enabled (Bearer token required)")
    else:
        print("Auth: disabled (set PEAKFLOW_ALPHA_TOKEN to enable)")
    server.serve_forever()


if __name__ == "__main__":
    main()
