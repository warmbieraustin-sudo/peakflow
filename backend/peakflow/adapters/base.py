from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Protocol


@dataclass
class RawBundle:
    source: str
    wellness_rows: List[Dict[str, Any]]
    activity_rows: List[Dict[str, Any]]


class ProviderAdapter(Protocol):
    source: str

    def fetch(self, oldest: str, newest: str) -> RawBundle:
        """Fetch raw provider records for the requested date range."""
        ...

    def normalize_wellness(self, row: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def normalize_activity(self, row: Dict[str, Any]) -> Dict[str, Any]:
        ...
