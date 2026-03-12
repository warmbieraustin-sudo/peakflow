# Beta Cohort Invite Flow (Day 29)

## Cohorts
1. **Coached athletes** (TrainingPeaks plan source)
2. **Self-coached athletes** (PeakFlow planning source)

## Invite sequence
1. Candidate identified (friend/waitlist)
2. Assign `athleteId`
3. Send invite message + expectations
4. Complete onboarding checklist
5. Run first-week review cadence

## Suggested invite message (short)
"Hey! I’m running a private PeakFlow beta for endurance athletes. It gives daily recommendations + workout reviews and adapts from your feedback. If you’re in, I’ll set up your athlete profile and we’ll run a 1-week guided test."

## Setup checklist per athlete
- [ ] `athleteId` assigned and saved
- [ ] Planner state available (`/api/alpha/planner/state?athleteId=<id>`)
- [ ] Data source connected (Intervals.icu required; TP optional for coached)
- [ ] Coach mode set correctly (on for coached, off for self-coached)
- [ ] First recommendation rendered in `/plan`
- [ ] Relevance feedback submitted at least once

## Week-1 cadence
- Day 1: setup + first recommendation
- Day 3: check relevance trend + friction points
- Day 7: short retrospective (what helped, what was confusing)

## Success criteria
- >=1 completed recommendation review cycle
- >=1 relevance feedback submission
- athlete reports recommendation quality >= 4/5 at least once
