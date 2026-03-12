from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_env() -> None:
    """Load environment values from common PeakFlow locations (non-destructive)."""
    backend_dir = Path(__file__).resolve().parents[1]
    project_root = backend_dir.parent

    candidates = [
        backend_dir / ".env",          # /peakflow/backend/.env
        project_root / ".env",         # /peakflow/.env
        Path.home() / ".openclaw" / "workspace" / ".env",  # existing local source
    ]
    for path in candidates:
        _load_dotenv(path)


def require_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required env var: {key}")
    return value
