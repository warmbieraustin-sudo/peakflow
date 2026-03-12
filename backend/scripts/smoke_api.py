#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = "/opt/homebrew/bin/python3"


def get_json(url: str, token: str | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except Exception:
            body = {"error": str(e)}
        return e.code, body


def main() -> int:
    ap = argparse.ArgumentParser(description="PeakFlow alpha API smoke test")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--token", default="")
    args = ap.parse_args()

    env = {**os.environ, "PYTHONPATH": str(ROOT), "PEAKFLOW_API_HOST": args.host, "PEAKFLOW_API_PORT": str(args.port)}
    if args.token:
        env["PEAKFLOW_ALPHA_TOKEN"] = args.token

    proc = subprocess.Popen([PY, "scripts/alpha_api.py"], cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1)
        base = f"http://{args.host}:{args.port}"

        checks = []

        status, body = get_json(base + "/api/health", token=args.token or None)
        checks.append(("health", status == 200 and body.get("ok") is True, status, body))

        status, body = get_json(base + "/api/alpha/routes", token=args.token or None)
        checks.append(("routes", status == 200 and body.get("ok") is True, status, body))

        status, body = get_json(base + "/api/alpha/shell/today", token=args.token or None)
        checks.append(("shell_today", status == 200 and body.get("ok") is True, status, body))

        status, body = get_json(base + "/api/alpha/workout/latest", token=args.token or None)
        checks.append(("workout_latest", status == 200 and body.get("ok") is True, status, body))

        status, body = get_json(base + "/api/alpha/planner/modalities", token=args.token or None)
        checks.append(("planner_modalities", status == 200 and body.get("ok") is True and isinstance(body.get("modalities"), list), status, body))

        status, body = get_json(base + "/api/alpha/planner/state?athleteId=default", token=args.token or None)
        checks.append(("planner_state", status == 200 and body.get("ok") is True and body.get("athlete_id") == "default", status, body))

        status, body = get_json(base + "/api/alpha/planner/feedback/log?athleteId=default&relevance=4&perceived=ok", token=args.token or None)
        checks.append(("planner_feedback_log", status == 200 and body.get("ok") is True and body.get("logged") is True, status, body))

        status, body = get_json(base + "/api/alpha/planner/feedback/summary", token=args.token or None)
        checks.append(("planner_feedback_summary", status == 200 and body.get("ok") is True and isinstance((body.get("summary") or {}).get("count"), int), status, body))

        status, body = get_json(base + "/api/alpha/planner/recommendation?sport=running", token=args.token or None)
        checks.append(("planner_reco", status == 200 and body.get("ok") is True and (body.get("payload") or {}).get("selected_sport") == "running", status, body))

        status, body = get_json(base + "/api/alpha/planner/recommendation?sport=cycling&coachMode=true", token=args.token or None)
        checks.append(("planner_reco_coach", status == 200 and body.get("ok") is True and (body.get("payload") or {}).get("coach_mode") is True, status, body))

        status, body = get_json(base + "/api/alpha/planner/horizon?sport=cycling&focusSport=cycling", token=args.token or None)
        checks.append(("planner_horizon", status == 200 and body.get("ok") is True and ((body.get("payload") or {}).get("horizon") or {}).get("firm_days") == 7, status, body))

        # if token mode enabled, verify unauthorized without token
        if args.token:
            status2, body2 = get_json(base + "/api/alpha/shell/today", token=None)
            checks.append(("auth_guard", status2 == 401, status2, body2))

        failed = [c for c in checks if not c[1]]
        for name, ok, status, _ in checks:
            print(f"[{name}] {'OK' if ok else 'FAIL'} status={status}")

        if failed:
            print("SMOKE_API_FAIL")
            return 1

        print("SMOKE_API_OK")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
