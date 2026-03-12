#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from datetime import date, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from peakflow.pwa_contract import build_alpha_shell_payload
from peakflow.workout_review import build_latest_workout_review
from peakflow.intervals import IntervalsClient
from peakflow.planner import SUPPORTED_SPORTS, build_daily_recommendation, build_horizon_plan

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT.parent / "frontend"
SILVER_DIR = ROOT / "data" / "silver"
ALPHA_TOKEN = os.environ.get("PEAKFLOW_ALPHA_TOKEN", "").strip()

DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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
                            "/api/alpha/planner/recommendation?sport=cycling",
                            "/api/alpha/planner/horizon?sport=cycling&focusSport=cycling",
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

            if path == "/api/alpha/planner/recommendation":
                q = parse_qs(parsed.query)
                day = (q.get("day") or [None])[0]
                sport = (q.get("sport") or ["cycling"])[0]
                focus_sport = (q.get("focusSport") or [None])[0]
                feedback_day = (q.get("feedbackDay") or [None])[0]
                if not feedback_day:
                    feedback_day = (date.today() - timedelta(days=1)).isoformat()

                shell = build_alpha_shell_payload(SILVER_DIR, day=day)
                review = build_latest_workout_review(day=feedback_day)
                payload = build_daily_recommendation(shell, sport, focus_sport=focus_sport, last_review=review)
                return _json(self, HTTPStatus.OK, {"ok": True, "payload": payload})

            if path == "/api/alpha/planner/horizon":
                q = parse_qs(parsed.query)
                day = (q.get("day") or [None])[0]
                sport = (q.get("sport") or ["cycling"])[0]
                focus_sport = (q.get("focusSport") or [None])[0]

                shell = build_alpha_shell_payload(SILVER_DIR, day=day)
                icu = IntervalsClient.from_env()
                newest = date.today().isoformat()
                oldest = (date.today() - timedelta(days=35)).isoformat()
                recent_activities = icu.activities(oldest, newest)

                payload = build_horizon_plan(shell, sport, focus_sport=focus_sport, recent_activities=recent_activities)
                return _json(self, HTTPStatus.OK, {"ok": True, "payload": payload})

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
