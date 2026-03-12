#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = "/opt/homebrew/bin/python3"
ENV = {"PYTHONPATH": str(ROOT)}


def run(cmd: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env={**__import__('os').environ, **ENV},
        capture_output=True,
        text=True,
        timeout=60,
    )
    return p.returncode, p.stdout, p.stderr


def main() -> int:
    steps = [
        ([PY, "scripts/intervals_snapshot.py", "--days", "1", "--silver", "--fresh-minutes", "180"], "bronze/silver ingest"),
        ([PY, "scripts/validate_silver.py"], "silver validation"),
        ([PY, "scripts/build_daily_gold.py", "--write"], "gold build"),
        ([PY, "scripts/query_daily.py"], "consumer contract query"),
    ]

    for cmd, label in steps:
        code, out, err = run(cmd)
        print(f"[{label}] exit={code}")
        if code != 0:
            if out.strip():
                print(out.strip())
            if err.strip():
                print(err.strip())
            return code

    print("SMOKE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
