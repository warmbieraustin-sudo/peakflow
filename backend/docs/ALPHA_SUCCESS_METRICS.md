# Alpha Success Metrics & Weekly Review Cadence (Day 28)

## North-star (alpha)
- Deliver recommendations athletes trust and act on.

## Core metrics (non-PII)
1. **Recommendation relevance**
   - Source: `/api/alpha/planner/feedback/log` (`relevance` 1-5)
   - Target: avg >= 3.8 after first 2 weeks

2. **Recommendation follow-through proxy**
   - Count sessions where execution exists within 24h of recommendation day
   - Segment by coachMode vs non-coachMode

3. **Confidence-quality alignment**
   - Compare high-confidence recommendations vs subsequent review score outcomes

4. **Coach mode plan source quality**
   - TP coverage: `tp_days_with_plan / total_days` from coach horizon summary
   - Target: >= 85% for coached cohort

5. **Adaptation usefulness**
   - Share of recommendations that change due to feedback/review (`modification_reason` != neutral)

## Weekly review cadence (30-45 min)
- **Monday:** inspect metric trends and biggest drops (relevance, TP coverage)
- **Wednesday:** review top reason_codes / modification_reasons and tune thresholds
- **Friday:** ship 1-2 targeted improvements, run smoke/tests, and note impact hypothesis

## Guardrails
- Keep logs non-PII (athleteId only)
- Prefer additive schema changes
- No destructive writes to TrainingPeaks
- Require smoke + unit + e2e green before merge
