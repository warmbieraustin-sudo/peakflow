#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from peakflow.pwa_contract import build_alpha_shell_payload


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate PeakFlow alpha PWA shell payload")
    p.add_argument("--day", type=str, default=None, help="Target day YYYY-MM-DD (default: latest)")
    p.add_argument("--write", action="store_true", help="Write payload to backend/data/app-shell/YYYY-MM-DD.json")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    silver = Path(__file__).resolve().parents[1] / "data" / "silver"
    payload = build_alpha_shell_payload(silver, day=args.day)
    if not payload:
        print("NO_DATA")
        return 1

    if args.write:
        out_dir = Path(__file__).resolve().parents[1] / "data" / "app-shell"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{payload['date']}.json"
        out_file.write_text(json.dumps(payload, indent=2))
        print(f"wrote {out_file}")

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
