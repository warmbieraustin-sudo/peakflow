"""
LLM Client for PeakFlow
Supports Claude (Anthropic) for narrative generation and reasoning.
"""

import os
import json
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from anthropic import Anthropic

class DailyDebrief(BaseModel):
    """Structured daily debrief output"""
    headline: str = Field(description="Short headline (1 sentence)")
    debrief: str = Field(description="Main narrative debrief (2-3 sentences)")
    today_focus: str = Field(description="Today's training focus (1 sentence)")

class LLMClient:
    """
    LLM client for PeakFlow alpha.
    Uses Claude Sonnet via Anthropic API.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-5"
    ):
        """
        Initialize LLM client.
        
        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env)
            model: Model ID (default: claude-sonnet-4-5)
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
        
        self.model = model
        self.client = Anthropic(api_key=self.api_key)
    
    def generate_debrief(
        self,
        recovery: Dict[str, Any],
        yesterday_workout: Optional[Dict[str, Any]] = None,
        load: Optional[Dict[str, Any]] = None
    ) -> DailyDebrief:
        """
        Generate daily recovery debrief using LLM.
        
        Args:
            recovery: Recovery metrics (sleep, HRV, RHR, weight)
            yesterday_workout: Yesterday's workout review (optional)
            load: Training load metrics (CTL, ATL, TSB) (optional)
        
        Returns:
            DailyDebrief with structured narrative
        """
        
        # Build context prompt
        prompt = self._build_debrief_prompt(recovery, yesterday_workout, load)
        
        # Call LLM with structured output
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=300,
                temperature=0.7,
                system="You are a professional endurance coach providing concise, actionable morning briefings to an athlete. Be direct, supportive, and data-driven. Use athlete-friendly language.",
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            # Parse response
            content = response.content[0].text
            
            # Try to extract JSON if wrapped in markdown
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()
            
            data = json.loads(json_str)
            return DailyDebrief(**data)
            
        except Exception as e:
            # Fallback to deterministic if LLM fails
            print(f"LLM debrief failed: {e}, using fallback")
            return self._fallback_debrief(recovery, yesterday_workout)
    
    def _build_debrief_prompt(
        self,
        recovery: Dict[str, Any],
        yesterday_workout: Optional[Dict[str, Any]],
        load: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for daily debrief generation."""
        
        prompt_parts = ["Generate a daily training debrief based on:\n"]
        
        # Recovery data
        prompt_parts.append("**Recovery:**")
        if 'sleep_score' in recovery:
            prompt_parts.append(f"- Sleep: {recovery['sleep_score']}/100")
        if 'sleep_seconds' in recovery:
            hours = recovery['sleep_seconds'] / 3600
            prompt_parts.append(f"- Sleep duration: {hours:.1f}h")
        if 'hrv' in recovery:
            prompt_parts.append(f"- HRV: {recovery['hrv']}ms")
        if 'resting_hr' in recovery:
            prompt_parts.append(f"- Resting HR: {recovery['resting_hr']} bpm")
        
        # Yesterday's workout context
        if yesterday_workout:
            exec_status = yesterday_workout.get('execution', {}).get('status')
            if exec_status == 'ok':
                activity = yesterday_workout.get('execution', {}).get('activity', {})
                workout_name = activity.get('name', 'session')
                intensity = activity.get('intensity', 'unknown')
                prompt_parts.append(f"\n**Yesterday:** Completed {workout_name} ({intensity} intensity)")
        
        # Training load
        if load:
            if 'ctl' in load and 'atl' in load:
                prompt_parts.append(f"\n**Load:** CTL {load['ctl']:.1f}, ATL {load['atl']:.1f}")
        
        prompt_parts.append("\nReturn ONLY valid JSON matching this schema:")
        prompt_parts.append('''{
  "headline": "<1 sentence status>",
  "debrief": "<2-3 sentence narrative linking recovery to yesterday's work>",
  "today_focus": "<1 sentence training focus for today>"
}''')
        
        return "\n".join(prompt_parts)
    
    def _fallback_debrief(
        self,
        recovery: Dict[str, Any],
        yesterday_workout: Optional[Dict[str, Any]]
    ) -> DailyDebrief:
        """Deterministic fallback when LLM fails."""
        
        sleep_score = recovery.get('sleep_score')
        hrv = recovery.get('hrv')
        
        if sleep_score and sleep_score >= 85:
            headline = "Recovery looks strong this morning"
            debrief = f"Sleep scored {sleep_score}/100 with solid HRV. You're ready for today's work."
        elif sleep_score and sleep_score < 75:
            headline = "Recovery signals are mixed"
            debrief = f"Sleep came in at {sleep_score}/100. Keep today's intensity controlled."
        else:
            headline = "Recovery data available"
            debrief = "Morning metrics are in. Check your readiness before today's session."
        
        today_focus = "Follow your planned workout and check in after training."
        
        return DailyDebrief(
            headline=headline,
            debrief=debrief,
            today_focus=today_focus
        )
