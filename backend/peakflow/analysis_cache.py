"""
Analysis caching system for PeakFlow.
Caches LLM-generated analysis to improve performance and reduce token spend.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional


class AnalysisCache:
    """
    Manages cached analysis results.
    Stores per-athlete analysis with timestamps and refresh tracking.
    """
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize analysis cache.
        
        Args:
            cache_dir: Directory for cache files (defaults to backend/data/cache)
        """
        if cache_dir is None:
            # Default to backend/data/cache
            base_dir = Path(__file__).parent.parent / "data" / "cache"
        else:
            base_dir = Path(cache_dir)
        
        self.cache_dir = base_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _cache_file(self, athlete_id: str) -> Path:
        """Get cache file path for athlete."""
        return self.cache_dir / f"analysis_{athlete_id}.json"
    
    def get(self, athlete_id: str = "default") -> Optional[Dict[str, Any]]:
        """
        Get cached analysis for athlete.
        
        Args:
            athlete_id: Athlete identifier
        
        Returns:
            Cached analysis dict or None if not available
        """
        cache_file = self._cache_file(athlete_id)
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            return data
        except Exception as e:
            print(f"Failed to read analysis cache: {e}")
            return None
    
    def set(
        self,
        insights: Dict[str, Any],
        athlete_id: str = "default",
        period_days: int = 14
    ) -> None:
        """
        Cache analysis results.
        
        Args:
            insights: Analysis insights dict
            athlete_id: Athlete identifier
            period_days: Analysis period (for metadata)
        """
        cache_file = self._cache_file(athlete_id)
        
        data = {
            "athlete_id": athlete_id,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "period_days": period_days,
            "insights": insights
        }
        
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Failed to write analysis cache: {e}")
    
    def is_stale(
        self,
        athlete_id: str = "default",
        max_age_hours: float = 6.0
    ) -> bool:
        """
        Check if cached analysis is stale.
        
        Args:
            athlete_id: Athlete identifier
            max_age_hours: Maximum age in hours before considered stale
        
        Returns:
            True if cache is stale or missing, False if fresh
        """
        cached = self.get(athlete_id)
        
        if not cached:
            return True
        
        generated_at_str = cached.get("generated_at")
        if not generated_at_str:
            return True
        
        try:
            generated_at = datetime.fromisoformat(generated_at_str.replace("Z", "+00:00"))
            age = datetime.utcnow().replace(tzinfo=generated_at.tzinfo) - generated_at
            return age > timedelta(hours=max_age_hours)
        except Exception:
            return True
    
    def should_refresh(
        self,
        athlete_id: str = "default",
        min_refresh_hours: float = 6.0
    ) -> bool:
        """
        Check if manual refresh is allowed (rate limiting).
        
        Args:
            athlete_id: Athlete identifier
            min_refresh_hours: Minimum hours between manual refreshes
        
        Returns:
            True if refresh is allowed, False if too soon
        """
        return self.is_stale(athlete_id, max_age_hours=min_refresh_hours)
