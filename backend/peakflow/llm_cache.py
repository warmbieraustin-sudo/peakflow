"""
LLM response caching for PeakFlow.
Caches debrief and workout explanations with smart invalidation.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional


class LLMCache:
    """
    Manages cached LLM responses with smart invalidation.
    """
    
    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize LLM cache."""
        if cache_dir is None:
            base_dir = Path(__file__).parent.parent / "data" / "cache"
        else:
            base_dir = Path(cache_dir)
        
        self.cache_dir = base_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _cache_file(self, cache_type: str, key: str) -> Path:
        """Get cache file path."""
        safe_key = key.replace('/', '_').replace(':', '-')
        return self.cache_dir / f"{cache_type}_{safe_key}.json"
    
    def get_debrief(self, date: str = None) -> Optional[Dict[str, Any]]:
        """
        Get cached debrief for a date.
        
        Args:
            date: ISO date (defaults to today)
        
        Returns:
            Cached debrief or None if stale/missing
        """
        if not date:
            date = datetime.now().isoformat()[:10]
        
        cache_file = self._cache_file("debrief", date)
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            # Debrief is valid for the whole day
            cached_date = data.get("date", "")[:10]
            if cached_date != date:
                return None
            
            return data.get("debrief")
        except Exception:
            return None
    
    def set_debrief(self, debrief: Dict[str, Any], date: str = None) -> None:
        """Cache debrief for a date."""
        if not date:
            date = datetime.now().isoformat()[:10]
        
        cache_file = self._cache_file("debrief", date)
        
        data = {
            "date": date,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "debrief": debrief
        }
        
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Failed to cache debrief: {e}")
    
    def get_workout_explanation(
        self,
        sport: str,
        athlete_id: str = "default",
        coach_mode: bool = False
    ) -> Optional[str]:
        """
        Get cached workout explanation.
        
        Args:
            sport: Sport type
            athlete_id: Athlete ID
            coach_mode: Coach mode enabled
        
        Returns:
            Cached explanation or None if stale/missing
        """
        today = datetime.now().isoformat()[:10]
        key = f"{athlete_id}_{sport}_{coach_mode}_{today}"
        cache_file = self._cache_file("explanation", key)
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            # Check if cached for today
            cached_date = data.get("date", "")[:10]
            if cached_date != today:
                return None
            
            # Check if sport or coach_mode changed
            if data.get("sport") != sport or data.get("coach_mode") != coach_mode:
                return None
            
            return data.get("explanation")
        except Exception:
            return None
    
    def set_workout_explanation(
        self,
        explanation: str,
        sport: str,
        athlete_id: str = "default",
        coach_mode: bool = False
    ) -> None:
        """Cache workout explanation."""
        today = datetime.now().isoformat()[:10]
        key = f"{athlete_id}_{sport}_{coach_mode}_{today}"
        cache_file = self._cache_file("explanation", key)
        
        data = {
            "date": today,
            "sport": sport,
            "coach_mode": coach_mode,
            "athlete_id": athlete_id,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "explanation": explanation
        }
        
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Failed to cache explanation: {e}")
