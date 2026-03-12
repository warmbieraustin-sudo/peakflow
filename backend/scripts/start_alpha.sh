#!/bin/bash
# PeakFlow Alpha API Startup Script
# Loads environment variables and starts server

set -e

# Load environment variables
if [ -f ~/.openclaw/workspace/.env ]; then
  export $(grep -v '^#' ~/.openclaw/workspace/.env | xargs)
fi

# Set API host
export PEAKFLOW_API_HOST=0.0.0.0
export PYTHONPATH=.

# Start server
exec python3 scripts/alpha_api.py
