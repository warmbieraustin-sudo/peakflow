"""
Athlete preferences schema and defaults.
"""
from typing import Dict, Any, List, Optional


DEFAULT_PREFERENCES = {
    "sports": ["cycling"],  # List of sports athlete does
    "weekly_hours": 10.0,  # Target weekly training hours
    "goals": "",  # Free-text goals/focus areas
    "height_cm": None,  # Height in cm (optional)
    "weight_kg": None,  # Current weight in kg (optional, auto-populated from Garmin)
}


def get_preferences(athlete_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get athlete preferences from state, with defaults for missing values.
    
    Args:
        athlete_state: Raw athlete state dict
    
    Returns:
        Preferences dict with defaults filled in
    """
    prefs = athlete_state.get("preferences", {})
    return {**DEFAULT_PREFERENCES, **prefs}


def validate_preferences(prefs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and sanitize preference inputs.
    
    Args:
        prefs: Raw preferences dict from API
    
    Returns:
        Validated preferences dict
    """
    validated = {}
    
    # Sports must be a list
    if "sports" in prefs:
        sports = prefs["sports"]
        if isinstance(sports, list):
            validated["sports"] = [s.strip().lower() for s in sports if s]
    
    # Weekly hours must be positive float
    if "weekly_hours" in prefs:
        try:
            hours = float(prefs["weekly_hours"])
            if hours > 0 and hours <= 50:  # Sanity cap at 50 hrs/week
                validated["weekly_hours"] = hours
        except (ValueError, TypeError):
            pass
    
    # Goals is free text
    if "goals" in prefs:
        goals = str(prefs["goals"]).strip()
        if goals:
            validated["goals"] = goals
    
    # Height in cm
    if "height_cm" in prefs:
        try:
            height = float(prefs["height_cm"])
            if 100 <= height <= 250:  # Reasonable human range
                validated["height_cm"] = height
        except (ValueError, TypeError):
            pass
    
    # Weight in kg
    if "weight_kg" in prefs:
        try:
            weight = float(prefs["weight_kg"])
            if 30 <= weight <= 200:  # Reasonable human range
                validated["weight_kg"] = weight
        except (ValueError, TypeError):
            pass
    
    return validated
