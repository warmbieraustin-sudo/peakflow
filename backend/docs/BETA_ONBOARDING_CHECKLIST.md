# PeakFlow Beta Onboarding Checklist (Day 27)

## Cohorts
- **Coached athletes (TrainingPeaks source-of-truth)**
- **Self-coached athletes (PeakFlow planner source-of-truth)**

## 1) Identity + Access
- [ ] Assign `athleteId`
- [ ] Confirm alpha token + URL access
- [ ] Verify planner state endpoint works (`/api/alpha/planner/state?athleteId=...`)

## 2) Data Connections
- [ ] Intervals.icu connected and recent activities available
- [ ] TrainingPeaks connected (coached cohort)
- [ ] Optional Garmin/WHOOP linked for readiness context

## 3) Planning Mode Setup
### Coached cohort
- [ ] Enable `coachMode=true`
- [ ] Confirm `plan_source=trainingpeaks`
- [ ] Confirm `non_destructive_overlay=true`

### Self-coached cohort
- [ ] Keep `coachMode=false`
- [ ] Confirm PeakFlow plan schema validates

## 4) Experience Validation
- [ ] User can choose today’s modality in `/plan`
- [ ] User can submit feedback (`easy|ok|hard`)
- [ ] Recommendation updates on next render with clear reason
- [ ] 7-day firm horizon renders with phase context

## 5) Quality Signals to Collect
- [ ] Recommendation relevance (1-5)
- [ ] Perceived fatigue match (too easy / right / too hard)
- [ ] Trust in explanation (“why this changed”)
- [ ] Coach acceptance of non-destructive overlay

## 6) Safety + Rollback
- [ ] If TP unavailable in coached mode, fallback plan appears with clear flag
- [ ] No destructive writes to TP
- [ ] Smoke checks pass before each deploy
