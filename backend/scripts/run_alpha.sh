#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export PYTHONPATH="$(pwd)"
export PEAKFLOW_API_HOST="${PEAKFLOW_API_HOST:-127.0.0.1}"
export PEAKFLOW_API_PORT="${PEAKFLOW_API_PORT:-8787}"

echo "🏔️ PeakFlow alpha starting on http://${PEAKFLOW_API_HOST}:${PEAKFLOW_API_PORT}"
if [[ -n "${PEAKFLOW_ALPHA_TOKEN:-}" ]]; then
  echo "🔐 Auth enabled (Bearer token required)"
else
  echo "🔓 Auth disabled (set PEAKFLOW_ALPHA_TOKEN to enable)"
fi

exec /opt/homebrew/bin/python3 scripts/alpha_api.py
