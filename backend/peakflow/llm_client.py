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

class WorkoutBlock(BaseModel):
    """Single workout interval/block"""
    label: str = Field(description="Block name (e.g., 'Warm up', 'Active', 'Cool Down')")
    duration_minutes: int = Field(description="Duration in minutes")
    target_low: Optional[int] = Field(None, description="Lower target (% or watts)")
    target_high: Optional[int] = Field(None, description="Upper target (% or watts)")
    target_type: str = Field("effort", description="power_pct_ftp, hr_pct_max, effort")
    description: str = Field(description="Human-readable block description")

class DailyWorkout(BaseModel):
    """Single day's workout plan"""
    sport_type: str = Field(description="cycling, running, hiking, yoga, strength, ski")
    title: str = Field(description="Workout title")
    duration_minutes: int = Field(description="Total duration")
    intensity: str = Field(description="easy, moderate, hard")
    blocks: list[WorkoutBlock] = Field(description="Workout structure")
    coach_notes: Optional[str] = Field(None, description="Coach commentary")

class WeeklyPlan(BaseModel):
    """7-day workout plan"""
    plan_type: str = Field(description="mixed_modality or single_sport")
    primary_sport: Optional[str] = Field(None, description="Primary sport if single_sport")
    workouts: dict[str, DailyWorkout] = Field(description="ISO date -> workout mapping")
    weekly_notes: str = Field(description="Week-level coaching notes")

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
    
    def explain_workout(
        self,
        recommendation: Dict[str, Any],
        recovery: Dict[str, Any],
        load: Optional[Dict[str, Any]] = None,
        recent_feedback: Optional[str] = None
    ) -> str:
        """
        Generate workout explanation using LLM.
        
        Args:
            recommendation: Today's workout recommendation
            recovery: Current recovery metrics
            load: Training load (CTL/ATL/TSB)
            recent_feedback: Recent athlete feedback (easy/ok/hard)
        
        Returns:
            Natural language explanation of why this workout was chosen
        """
        
        prompt_parts = ["Explain why this workout was recommended:\n"]
        
        # Workout details
        workout_title = recommendation.get('plan', {}).get('title', 'session')
        intensity = recommendation.get('intensity_band', 'moderate')
        prompt_parts.append(f"**Workout:** {workout_title} ({intensity} intensity)")
        
        # Recovery context
        if 'sleep_score' in recovery:
            prompt_parts.append(f"**Recovery:** Sleep {recovery['sleep_score']}/100")
        if 'hrv' in recovery:
            prompt_parts.append(f", HRV {recovery['hrv']}ms")
        
        # Load context
        if load and 'ctl' in load and 'atl' in load:
            tsb = load.get('ctl', 0) - load.get('atl', 0)
            prompt_parts.append(f"\n**Load:** CTL {load['ctl']:.1f}, ATL {load['atl']:.1f}, TSB {tsb:.1f}")
        
        # Feedback context
        if recent_feedback:
            prompt_parts.append(f"\n**Recent feedback:** Yesterday felt {recent_feedback}")
        
        # Coach mode context
        if recommendation.get('plan_source') == 'trainingpeaks':
            prompt_parts.append("\n**Note:** This workout comes from your TrainingPeaks plan.")
        
        prompt_parts.append("\n\nProvide a 2-3 sentence coaching explanation in plain text (no JSON).")
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                temperature=0.7,
                system="You are a professional endurance coach explaining workout choices to an athlete. Be concise, supportive, and connect the workout to their current state.",
                messages=[{
                    "role": "user",
                    "content": "\n".join(prompt_parts)
                }]
            )
            
            return response.content[0].text.strip()
            
        except Exception as e:
            print(f"LLM workout explanation failed: {e}")
            return f"This {intensity} intensity session is appropriate given your current recovery and training load."
    
    def generate_weekly_plan(
        self,
        start_date: str,
        athlete_preferences: Dict[str, Any],
        recovery: Dict[str, Any],
        load: Optional[Dict[str, Any]] = None,
        recent_workouts: Optional[list[Dict[str, Any]]] = None
    ) -> WeeklyPlan:
        """
        Generate 7-day workout plan using LLM.
        
        Args:
            start_date: ISO date for week start (e.g., "2026-03-12")
            athlete_preferences: Sport mix, weekly hours, goals
            recovery: Current recovery state
            load: Training load (CTL/ATL/TSB)
            recent_workouts: Recent workout history for context
        
        Returns:
            WeeklyPlan with daily workouts
        """
        
        prompt = self._build_weekly_plan_prompt(
            start_date, athlete_preferences, recovery, load, recent_workouts
        )
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.7,
                system="You are a professional endurance coach building adaptive weekly training plans. Generate detailed, sport-specific workouts with proper progression and recovery. Return ONLY valid JSON.",
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            content = response.content[0].text
            
            # Extract JSON
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()
            
            data = json.loads(json_str)
            return WeeklyPlan(**data)
            
        except Exception as e:
            print(f"LLM weekly plan failed: {e}, using fallback")
            return self._fallback_weekly_plan(start_date, athlete_preferences)
    
    def _build_weekly_plan_prompt(
        self,
        start_date: str,
        athlete_preferences: Dict[str, Any],
        recovery: Dict[str, Any],
        load: Optional[Dict[str, Any]],
        recent_workouts: Optional[list[Dict[str, Any]]]
    ) -> str:
        """Build prompt for weekly plan generation."""
        
        prompt_parts = ["Generate a 7-day training plan based on:\n"]
        
        # Athlete preferences
        prompt_parts.append("**Athlete Profile:**")
        weekly_hours = athlete_preferences.get('weekly_hours', 10)
        primary_sport = athlete_preferences.get('primary_sport', 'cycling')
        sports = athlete_preferences.get('sports', [primary_sport])
        goal = athlete_preferences.get('goal', 'Build endurance and consistency')
        
        prompt_parts.append(f"- Weekly training time: {weekly_hours} hours")
        prompt_parts.append(f"- Sports: {', '.join(sports)}")
        prompt_parts.append(f"- Goal: {goal}")
        
        # Current state
        prompt_parts.append("\n**Current State:**")
        if 'sleep_score' in recovery:
            prompt_parts.append(f"- Recovery: Sleep {recovery['sleep_score']}/100")
        if load and 'ctl' in load:
            prompt_parts.append(f"- Fitness (CTL): {load['ctl']:.1f}")
        
        # Recent context
        if recent_workouts:
            prompt_parts.append(f"\n**Recent workouts:** {len(recent_workouts)} sessions in past week")
        
        prompt_parts.append(f"\n**Week start date:** {start_date}")
        
        # Schema
        prompt_parts.append("\nReturn ONLY valid JSON matching this schema:")
        prompt_parts.append('''{
  "plan_type": "mixed_modality" or "single_sport",
  "primary_sport": "<sport>" or null,
  "workouts": {
    "2026-03-12": {
      "sport_type": "cycling",
      "title": "Recovery Ride",
      "duration_minutes": 60,
      "intensity": "easy",
      "blocks": [
        {
          "label": "Warm up",
          "duration_minutes": 5,
          "target_low": 45,
          "target_high": 55,
          "target_type": "power_pct_ftp",
          "description": "5min easy spin"
        },
        {
          "label": "Active",
          "duration_minutes": 50,
          "target_low": 40,
          "target_high": 50,
          "target_type": "power_pct_ftp",
          "description": "50min @ Z1-Z2"
        },
        {
          "label": "Cool Down",
          "duration_minutes": 5,
          "target_low": 45,
          "target_high": null,
          "target_type": "power_pct_ftp",
          "description": "5min easy spin"
        }
      ],
      "coach_notes": "Easy day to promote recovery"
    },
    ... (6 more days)
  },
  "weekly_notes": "<week-level coaching summary>"
}''')
        
        prompt_parts.append("\n**IMPORTANT Guidelines:**")
        prompt_parts.append("1. **Multi-sport athletes:** If multiple sports listed, use plan_type='mixed_modality' and vary sports across the week")
        prompt_parts.append("2. **Single-sport athletes:** If only one sport listed, use plan_type='single_sport' and set primary_sport")
        prompt_parts.append("3. **Polarized training:** 80% easy, 20% hard (include at least 1-2 easy recovery days)")
        prompt_parts.append("4. **Sport-specific targets:**")
        prompt_parts.append("   - Cycling/VirtualRide: target_type='power_pct_ftp', targets in % FTP")
        prompt_parts.append("   - Running: target_type='pace', targets in min/mile or min/km")
        prompt_parts.append("   - Strength/Yoga: target_type='effort', targets as perceived effort (1-10)")
        prompt_parts.append("   - Swimming: target_type='pace', targets in min/100m")
        prompt_parts.append("5. **Weekly volume:** Total weekly minutes should match athlete's weekly_hours × 60")
        prompt_parts.append("6. **Rest days:** Include at least 1 complete rest day (duration_minutes=0, empty blocks[])")
        
        return "\n".join(prompt_parts)
    
    def _fallback_weekly_plan(
        self,
        start_date: str,
        athlete_preferences: Dict[str, Any]
    ) -> WeeklyPlan:
        """Deterministic fallback weekly plan when LLM fails."""
        
        from datetime import datetime, timedelta
        
        start = datetime.fromisoformat(start_date)
        primary_sport = athlete_preferences.get('primary_sport', 'cycling')
        sports = athlete_preferences.get('sports', [primary_sport])
        is_multi_sport = len(sports) > 1
        
        # Simple 7-day pattern: easy, moderate, easy, hard, easy, moderate, rest
        pattern = ['easy', 'moderate', 'easy', 'hard', 'easy', 'moderate', 'rest']
        
        # For multi-sport, rotate through sports
        sport_rotation = sports if is_multi_sport else [primary_sport]
        
        workouts = {}
        sport_idx = 0
        
        for i in range(7):
            day = (start + timedelta(days=i)).isoformat()
            intensity = pattern[i]
            
            if intensity == 'rest':
                workouts[day] = DailyWorkout(
                    sport_type=sport_rotation[0],
                    title="Rest Day",
                    duration_minutes=0,
                    intensity="easy",
                    blocks=[],
                    coach_notes="Recovery day"
                )
            else:
                sport = sport_rotation[sport_idx % len(sport_rotation)]
                sport_idx += 1
                
                duration = 90 if intensity == 'hard' else 60
                
                # Sport-specific target types
                if sport in ('cycling', 'ride', 'virtualride'):
                    target_type = "power_pct_ftp"
                    target_low = 40 if intensity == 'easy' else 70
                    target_high = 60 if intensity == 'easy' else 85
                elif sport in ('running', 'run', 'virtualrun'):
                    target_type = "pace"
                    target_low = None
                    target_high = None
                elif sport in ('yoga', 'stretching', 'strength', 'workout'):
                    target_type = "effort"
                    target_low = 3 if intensity == 'easy' else 7
                    target_high = 5 if intensity == 'easy' else 9
                else:
                    target_type = "effort"
                    target_low = None
                    target_high = None
                
                workouts[day] = DailyWorkout(
                    sport_type=sport,
                    title=f"{intensity.capitalize()} {sport}",
                    duration_minutes=duration,
                    intensity=intensity,
                    blocks=[
                        WorkoutBlock(
                            label="Main",
                            duration_minutes=duration,
                            target_low=target_low,
                            target_high=target_high,
                            target_type=target_type,
                            description=f"{duration}min {intensity} effort"
                        )
                    ],
                    coach_notes=f"{intensity.capitalize()} training session"
                )
        
        return WeeklyPlan(
            plan_type="mixed_modality" if is_multi_sport else "single_sport",
            primary_sport=primary_sport if not is_multi_sport else None,
            workouts=workouts,
            weekly_notes="Mixed-sport training plan with polarized intensity distribution" if is_multi_sport else "Polarized training plan with mixed intensities"
        )
    
    def generate_analysis_insights(
        self,
        recent_workouts: list[Dict[str, Any]],
        recovery_trend: list[Dict[str, Any]],
        load_trend: Optional[list[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate performance and recovery trend analysis.
        
        Args:
            recent_workouts: Recent workout history (last 7-30 days)
            recovery_trend: Recovery metrics over time
            load_trend: Training load progression (optional)
        
        Returns:
            Dict with insights, trends, and recommendations
        """
        
        prompt_parts = ["Analyze this athlete's recent training and recovery:\n"]
        
        # Workout summary
        if recent_workouts:
            prompt_parts.append(f"**Recent workouts:** {len(recent_workouts)} sessions")
            intensities = [w.get('intensity', 'unknown') for w in recent_workouts]
            easy_count = intensities.count('easy')
            hard_count = intensities.count('hard') + intensities.count('moderate')
            prompt_parts.append(f"- Easy: {easy_count}, Hard: {hard_count}")
        
        # Recovery trend with more detail
        if recovery_trend:
            sleep_scores = [r.get('sleep_score', 0) for r in recovery_trend if r.get('sleep_score')]
            hrv_values = [r.get('hrv', 0) for r in recovery_trend if r.get('hrv')]
            
            if sleep_scores:
                avg_sleep = sum(sleep_scores) / len(sleep_scores)
                min_sleep = min(sleep_scores)
                max_sleep = max(sleep_scores)
                prompt_parts.append(f"\n**Recovery trend (last {len(recovery_trend)} days):**")
                prompt_parts.append(f"- Sleep score: avg {avg_sleep:.0f}/100, range {min_sleep:.0f}-{max_sleep:.0f}")
            
            if hrv_values:
                avg_hrv = sum(hrv_values) / len(hrv_values)
                min_hrv = min(hrv_values)
                max_hrv = max(hrv_values)
                prompt_parts.append(f"- HRV: avg {avg_hrv:.0f}ms, range {min_hrv:.0f}-{max_hrv:.0f}ms")
                
            # Highlight last 3 days specifically
            recent_3 = recovery_trend[:3]  # most recent 3 days
            if len(recent_3) >= 2:
                recent_sleep = [r.get('sleep_score') for r in recent_3 if r.get('sleep_score')]
                if recent_sleep:
                    prompt_parts.append(f"- Last 3 nights sleep: {', '.join(str(int(s)) for s in recent_sleep)}")
            
            prompt_parts.append("**IMPORTANT:** Analyze the 14-day TREND, not just the most recent night. Look for patterns, consistency, and changes over time.")
        
        # Load trend
        if load_trend:
            prompt_parts.append(f"\n**Load progression:** {len(load_trend)} days")
            latest = load_trend[-1]
            if 'ctl' in latest:
                prompt_parts.append(f"- Current CTL: {latest['ctl']:.1f}")
        
        prompt_parts.append("\nGenerate insights as JSON:")
        prompt_parts.append('''{
  "performance_insights": [
    "<insight 1>",
    "<insight 2>"
  ],
  "recovery_insights": [
    "<insight 1>",
    "<insight 2>"
  ],
  "recommendations": [
    "<actionable recommendation 1>",
    "<actionable recommendation 2>"
  ],
  "summary": "<1-2 sentence overview>"
}''')
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=600,
                temperature=0.7,
                system="You are a data-driven endurance coach analyzing training trends. Provide actionable insights based on patterns in the athlete's data.",
                messages=[{
                    "role": "user",
                    "content": "\n".join(prompt_parts)
                }]
            )
            
            content = response.content[0].text
            
            # Extract JSON
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()
            
            return json.loads(json_str)
            
        except Exception as e:
            print(f"LLM analysis insights failed: {e}")
            return {
                "performance_insights": ["Workout data available"],
                "recovery_insights": ["Recovery data available"],
                "recommendations": ["Continue with planned training"],
                "summary": "Keep training consistently"
            }
    
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
    
    def chat(
        self,
        message: str,
        history: list[Dict[str, str]],
        preferences: Dict[str, Any],
        recovery: Dict[str, Any],
        load: Dict[str, Any],
        recent_workouts: list[Dict[str, Any]]
    ) -> str:
        """
        Conversational chat interface with full context.
        Supports training questions AND app navigation help.
        
        Args:
            message: User's message
            history: Chat history (list of {role, content} dicts)
            preferences: Athlete preferences
            recovery: Current recovery metrics
            load: Current training load
            recent_workouts: Recent workout history
        
        Returns:
            Assistant response
        """
        # Build context
        context_parts = ["**Athlete Context:**"]
        
        # Preferences
        if preferences:
            sports = preferences.get("sports", [])
            weekly_hours = preferences.get("weekly_hours")
            goals = preferences.get("goals")
            weight = preferences.get("weight_kg")
            
            if sports:
                context_parts.append(f"- Sports: {', '.join(sports)}")
            if weekly_hours:
                context_parts.append(f"- Weekly hours target: {weekly_hours}")
            if goals:
                context_parts.append(f"- Goals: {goals}")
            if weight:
                context_parts.append(f"- Current weight: {weight}kg")
        
        # Recovery
        if recovery:
            sleep = recovery.get("sleep_score")
            hrv = recovery.get("hrv")
            rhr = recovery.get("resting_hr")
            
            if sleep:
                context_parts.append(f"- Sleep: {sleep}/100")
            if hrv:
                context_parts.append(f"- HRV: {hrv}ms")
            if rhr:
                context_parts.append(f"- Resting HR: {rhr}bpm")
        
        # Load
        if load:
            ctl = load.get("ctl")
            atl = load.get("atl")
            tsb = load.get("tsb")
            
            if ctl:
                context_parts.append(f"- Fitness (CTL): {ctl:.1f}")
            if atl:
                context_parts.append(f"- Fatigue (ATL): {atl:.1f}")
            if tsb:
                context_parts.append(f"- Form (TSB): {tsb:.1f}")
        
        # Recent workouts (last 3)
        if recent_workouts:
            context_parts.append(f"\n**Recent workouts ({len(recent_workouts[:3])} shown):**")
            for w in recent_workouts[:3]:
                sport = w.get("type", "workout")
                duration_sec = w.get("moving_time", 0)
                duration_min = duration_sec / 60
                context_parts.append(f"- {sport}: {duration_min:.0f}min")
        
        # System prompt
        system_prompt = """You are a helpful AI training assistant for PeakFlow.

Your role:
1. Answer questions about training, recovery, performance, and planning
2. Help users understand and navigate the PeakFlow app
3. Explain training metrics (TSS, CTL, ATL, TSB, power zones, etc.)
4. Provide coaching guidance based on available data
5. Help with app features (how to use preferences, view plans, track progress)

Guidelines:
- Be conversational and encouraging
- Cite specific data when giving advice
- Explain technical terms if user seems unsure
- If asked about app features, provide clear navigation instructions
- Always prioritize athlete safety and sustainable training
- If you don't have enough data, say so clearly

For app help questions:
- Preferences: Set sports, goals, and weekly hours targets
- Recovery: View sleep, HRV, and readiness metrics
- Today's Workout: See daily recommendation and workout details
- 7-Day Plan: View training horizon and intensity pattern
- Analysis: Review 14-day performance and recovery trends
- Chat: This page! Ask questions anytime"""

        # Construct messages
        messages = []
        
        # Add context as first user message if history is empty
        if not history:
            messages.append({
                "role": "user",
                "content": "\n".join(context_parts)
            })
            messages.append({
                "role": "assistant",
                "content": "Got it! I have your current context. How can I help you today?"
            })
        
        # Add history
        messages.extend(history[-10:])  # Last 10 messages (5 exchanges)
        
        # Add current message
        messages.append({
            "role": "user",
            "content": message
        })
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                temperature=0.7,
                system=system_prompt,
                messages=messages
            )
            
            return response.content[0].text
        
        except Exception as e:
            print(f"LLM chat failed: {e}")
            return "I'm having trouble connecting right now. Please try again in a moment."
