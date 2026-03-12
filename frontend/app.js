const TOKEN_KEY = 'peakflow_alpha_token';
const ADVANCED_KEY = 'peakflow_advanced_ui';

// Session-memory cache (resets on page reload)
const MEMORY_CACHE = new Map();

function cacheGet(key, ttlMs = 120000) {
  const hit = MEMORY_CACHE.get(key);
  if (!hit) return null;
  if (Date.now() - hit.ts > ttlMs) {
    MEMORY_CACHE.delete(key);
    return null;
  }
  return hit.value;
}

function cacheSet(key, value) {
  MEMORY_CACHE.set(key, { ts: Date.now(), value });
}

function cacheInvalidate(prefixes = []) {
  for (const key of MEMORY_CACHE.keys()) {
    if (prefixes.some(p => key.startsWith(p))) MEMORY_CACHE.delete(key);
  }
}

function getToken() {
  return localStorage.getItem(TOKEN_KEY) || '';
}

function setToken(token) {
  if (!token) localStorage.removeItem(TOKEN_KEY);
  else localStorage.setItem(TOKEN_KEY, token.trim());
}

function isAdvancedUi() {
  return localStorage.getItem(ADVANCED_KEY) === '1';
}

function setAdvancedUi(on) {
  localStorage.setItem(ADVANCED_KEY, on ? '1' : '0');
}

async function apiGet(path, { cacheKey = null, ttlMs = 120000, bypassCache = false } = {}) {
  if (cacheKey && !bypassCache) {
    const cached = cacheGet(cacheKey, ttlMs);
    if (cached) return cached;
  }

  const token = getToken();
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(path, { headers });
  const body = await res.json().catch(() => ({}));
  const out = { ok: res.ok, status: res.status, body };

  if (cacheKey && res.ok) cacheSet(cacheKey, out);
  return out;
}

async function apiPost(path, data) {
  const token = getToken();
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(path, {
    method: 'POST',
    headers,
    body: JSON.stringify(data)
  });
  const body = await res.json().catch(() => ({}));
  const out = { ok: res.ok, status: res.status, body };

  // Invalidate affected cache groups after writes
  if (res.ok) {
    if (path.includes('/preferences')) cacheInvalidate(['preferences:', 'plan-horizon:', 'plan-reco:', 'llm-weekly:']);
    if (path.includes('/llm/chat')) cacheInvalidate(['preferences:', 'plan-horizon:', 'plan-reco:']);
  }

  return out;
}

async function fetchPayload() {
  const r = await apiGet('/api/alpha/shell/today', { cacheKey: 'shell:today', ttlMs: 60000 });
  if (!r.ok) throw new Error(r.body.error || `http_${r.status}`);
  return r.body.payload;
}

async function fetchWorkoutReview(day) {
  const qs = day ? `?day=${encodeURIComponent(day)}` : '';
  const key = `workout-review:${day || 'today'}`;
  const r = await apiGet(`/api/alpha/workout/latest${qs}`, { cacheKey: key, ttlMs: 120000 });
  if (!r.ok) throw new Error(r.body.error || `http_${r.status}`);
  return r.body.payload;
}

async function fetchLLMDebrief() {
  const r = await apiGet('/api/alpha/llm/debrief/today', { cacheKey: 'llm:debrief:today', ttlMs: 300000 });
  if (!r.ok) return null; // fallback to deterministic
  return r.body.debrief;
}

async function fetchLLMWorkoutExplanation(sport, athleteId, coachMode) {
  const qs = new URLSearchParams({
    sport: sport || 'cycling',
    athleteId: athleteId || 'default',
    coachMode: coachMode ? 'true' : 'false'
  });
  const key = `llm:explain:${sport || 'cycling'}:${athleteId || 'default'}:${coachMode ? '1' : '0'}`;
  const r = await apiGet(`/api/alpha/llm/explain-workout?${qs.toString()}`, { cacheKey: key, ttlMs: 300000 });
  if (!r.ok) return null;
  return r.body.explanation;
}

async function fetchLLMWeeklyPlan(startDate, athleteId) {
  const qs = new URLSearchParams({
    startDate: startDate || getTodayISO(),
    athleteId: athleteId || 'default'
  });
  const key = `llm-weekly:${startDate || getTodayISO()}:${athleteId || 'default'}`;
  const r = await apiGet(`/api/alpha/llm/weekly-plan?${qs.toString()}`, { cacheKey: key, ttlMs: 300000 });
  if (!r.ok) return null;
  return r.body.plan;
}

async function fetchLLMAnalysis(forceRefresh = false) {
  const qs = forceRefresh ? '?refresh=true' : '';
  const r = await apiGet(`/api/alpha/llm/analysis${qs}`, {
    cacheKey: forceRefresh ? null : 'llm:analysis',
    ttlMs: 180000,
    bypassCache: forceRefresh
  });
  if (!r.ok) return null;
  return {
    insights: r.body.insights,
    cached: r.body.cached || false,
    generated_at: r.body.generated_at
  };
}

async function fetchTodaysWorkoutAnalysis() {
  const r = await apiGet('/api/alpha/llm/workout-analysis/today', { cacheKey: 'llm:workout-analysis:today', ttlMs: 180000 });
  if (!r.ok) return null;
  return {
    analysis: r.body.analysis,
    cached: r.body.cached || false
  };
}

async function fetchPreferences() {
  const athleteId = getAthleteId();
  const r = await apiGet(`/api/alpha/preferences?athleteId=${encodeURIComponent(athleteId)}`, {
    cacheKey: `preferences:${athleteId}`,
    ttlMs: 300000
  });
  if (!r.ok) return null;
  return r.body.preferences;
}

async function savePreferences(prefs) {
  const athleteId = getAthleteId();
  const r = await apiPost('/api/alpha/preferences', {
    athleteId,
    preferences: prefs
  });
  return r.ok;
}

async function sendChatMessage(message) {
  const athleteId = getAthleteId();
  const r = await apiPost('/api/alpha/llm/chat', {
    athleteId,
    message
  });
  if (!r.ok) throw new Error(r.body.error || 'chat_failed');
  return r.body.response;
}

const SPORT_KEY = 'peakflow_selected_sport';
const FOCUS_SPORT_KEY = 'peakflow_focus_sport';
const ATHLETE_FEEDBACK_KEY = 'peakflow_athlete_feedback';
const COACH_MODE_KEY = 'peakflow_coach_mode';
const ATHLETE_ID_KEY = 'peakflow_athlete_id';

function getSelectedSport() {
  return localStorage.getItem(SPORT_KEY) || 'cycling';
}

function setSelectedSport(s) {
  localStorage.setItem(SPORT_KEY, s || 'cycling');
}

function getFocusSport() {
  return localStorage.getItem(FOCUS_SPORT_KEY) || 'cycling';
}

function setFocusSport(s) {
  localStorage.setItem(FOCUS_SPORT_KEY, s || 'cycling');
}

function getAthleteFeedback() {
  return localStorage.getItem(ATHLETE_FEEDBACK_KEY) || '';
}

function setAthleteFeedback(v) {
  if (!v) localStorage.removeItem(ATHLETE_FEEDBACK_KEY);
  else localStorage.setItem(ATHLETE_FEEDBACK_KEY, v);
}

function getCoachMode() {
  return localStorage.getItem(COACH_MODE_KEY) === '1';
}

function setCoachMode(on) {
  localStorage.setItem(COACH_MODE_KEY, on ? '1' : '0');
}

function getAthleteId() {
  return localStorage.getItem(ATHLETE_ID_KEY) || 'default';
}

function setAthleteId(v) {
  if (!v) localStorage.removeItem(ATHLETE_ID_KEY);
  else localStorage.setItem(ATHLETE_ID_KEY, v.trim());
}

async function fetchModalities() {
  const r = await apiGet('/api/alpha/planner/modalities', { cacheKey: 'plan:modalities', ttlMs: 600000 });
  if (!r.ok) throw new Error(r.body.error || `http_${r.status}`);
  return r.body.modalities || [];
}

async function fetchPlannerState(athleteId) {
  const id = athleteId || 'default';
  const qs = new URLSearchParams({ athleteId: id });
  const r = await apiGet(`/api/alpha/planner/state?${qs.toString()}`, { cacheKey: `plan-state:${id}`, ttlMs: 120000 });
  if (!r.ok) throw new Error(r.body.error || `http_${r.status}`);
  return r.body.state || {};
}

async function fetchPlanRecommendation(sport, focusSport, athleteFeedback, coachMode, athleteId) {
  const id = athleteId || 'default';
  const qs = new URLSearchParams({
    sport: sport || 'cycling',
    focusSport: focusSport || '',
    athleteId: id,
    coachMode: coachMode ? 'true' : 'false',
  });
  if (athleteFeedback) qs.set('athleteFeedback', athleteFeedback);
  const key = `plan-reco:${id}:${sport || 'cycling'}:${focusSport || ''}:${coachMode ? '1' : '0'}:${athleteFeedback || ''}`;
  const r = await apiGet(`/api/alpha/planner/recommendation?${qs.toString()}`, { cacheKey: key, ttlMs: 90000 });
  if (!r.ok) throw new Error(r.body.error || `http_${r.status}`);
  return r.body.payload;
}

async function fetchPlanHorizon(sport, focusSport, athleteId, coachMode) {
  const id = athleteId || 'default';
  const qs = new URLSearchParams({
    sport: sport || 'cycling',
    focusSport: focusSport || '',
    athleteId: id,
    coachMode: coachMode ? 'true' : 'false',
  });
  const key = `plan-horizon:${id}:${sport || 'cycling'}:${focusSport || ''}:${coachMode ? '1' : '0'}`;
  const r = await apiGet(`/api/alpha/planner/horizon?${qs.toString()}`, { cacheKey: key, ttlMs: 120000 });
  if (!r.ok) throw new Error(r.body.error || `http_${r.status}`);
  return r.body.payload;
}

async function logRecommendationFeedback({ athleteId, relevance, perceived, recId, note }) {
  const qs = new URLSearchParams({ athleteId: athleteId || 'default' });
  if (relevance != null) qs.set('relevance', String(relevance));
  if (perceived) qs.set('perceived', perceived);
  if (recId) qs.set('recId', recId);
  if (note) qs.set('note', note);
  const r = await apiGet(`/api/alpha/planner/feedback/log?${qs.toString()}`);
  if (!r.ok) throw new Error(r.body.error || `http_${r.status}`);
  return r.body;
}

function card(label, value) {
  return `<div class="card"><div class="label">${label}</div><div class="value">${value ?? '—'}</div></div>`;
}

function renderMorning(p) {
  const m = p.screens.morning_brief;
  const freshStatus = m.headline.fresh ? '✅ Fresh' : '⚠️ Stale';
  return `
    <div class="card">
      <div class="label">Data Status</div>
      <div class="value">${freshStatus}</div>
      <div class="muted">Updated ${m.headline.freshness_age_minutes ?? '—'} minutes ago</div>
    </div>
    
    <div class="card">
      <div class="label">Recovery Snapshot</div>
      <div class="row">
        ${card('Weight (kg)', m.quick_recovery.weight_kg ?? '—')}
        ${card('Resting HR', m.quick_recovery.resting_hr ?? '—')}
        ${card('HRV', m.quick_recovery.hrv ?? '—')}
        ${card('Sleep Score', m.quick_recovery.sleep_score ?? '—')}
      </div>
    </div>
    
    <div class="card">
      <div class="label">Training Load</div>
      <div class="row">
        ${card('CTL', m.quick_load.ctl ?? '—')}
        ${card('ATL', m.quick_load.atl ?? '—')}
        ${card('Daily TL', m.quick_load.daily_training_load ?? '—')}
      </div>
    </div>
  `;
}

function getBlockColor(block) {
  const target = block.target_type || '';
  const low = block.target_low || 0;
  
  if (target.includes('power_pct_ftp')) {
    if (low < 55) return '#4a9eff'; // recovery/easy blue
    if (low < 75) return '#10b981'; // endurance green
    if (low < 90) return '#f59e0b'; // tempo orange
    if (low < 105) return '#ef4444'; // threshold red
    return '#dc2626'; // VO2/anaerobic dark red
  }
  
  if (target.includes('hr_pct_max')) {
    if (low < 70) return '#4a9eff';
    if (low < 80) return '#10b981';
    if (low < 90) return '#f59e0b';
    return '#ef4444';
  }
  
  return '#6b7690'; // default muted
}

function formatDuration(seconds) {
  if (!seconds) return '—';
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (secs === 0) return `${mins}min`;
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

function renderWorkoutGraph(blocks) {
  if (!blocks || blocks.length === 0) return '';
  
  const totalDuration = blocks.reduce((sum, b) => sum + (b.duration_sec || 0), 0);
  if (totalDuration === 0) return '';
  
  const maxHeightPx = 64; // max bar height in pixels
  const maxDuration = Math.max(...blocks.map(b => b.duration_sec || 0));
  
  const bars = blocks.map(b => {
    const heightPx = Math.round(((b.duration_sec || 0) / maxDuration) * maxHeightPx);
    const widthPct = ((b.duration_sec || 0) / totalDuration) * 100;
    const color = getBlockColor(b);
    const targetRange = b.target_low && b.target_high 
      ? `${b.target_low}-${b.target_high}%`
      : '—';
    
    return `
      <div style="
        flex: ${widthPct};
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
        align-items: center;
        min-width: 8px;
      " title="${b.label}: ${formatDuration(b.duration_sec)} @ ${targetRange}">
        <div style="
          width: 100%;
          background: ${color};
          height: ${heightPx}px;
          border-radius: 4px 4px 0 0;
          min-height: 4px;
        "></div>
      </div>
    `;
  }).join('');
  
  return `
    <div style="
      display: flex;
      gap: 6px;
      width: 100%;
      height: ${maxHeightPx + 16}px;
      align-items: flex-end;
      padding: 8px;
      background: rgba(0,0,0,0.15);
      border-radius: 8px;
      margin-bottom: 16px;
    ">
      ${bars}
    </div>
  `;
}

function formatTargetType(targetType) {
  if (!targetType) return '';
  if (targetType === 'power_pct_ftp') return 'FTP';
  if (targetType === 'hr_pct_max') return 'HR Max';
  if (targetType === 'power_watts') return 'Watts';
  if (targetType === 'hr_bpm') return 'BPM';
  return targetType.replace(/_/g, ' ');
}

function renderWorkoutBlocks(blocks) {
  if (!blocks || blocks.length === 0) return '';
  
  return blocks.map(b => {
    const duration = formatDuration(b.duration_sec);
    
    // Build target display
    let targetDisplay = 'Easy effort';
    if (b.target_low != null && b.target_high != null) {
      targetDisplay = `${b.target_low}-${b.target_high}% ${formatTargetType(b.target_type)}`;
    } else if (b.target_low != null) {
      targetDisplay = `${b.target_low}% ${formatTargetType(b.target_type)}`;
    }
    
    const color = getBlockColor(b);
    
    return `
      <div style="
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 8px 0;
        border-bottom: 1px solid var(--border, #1a1f2e);
      ">
        <div style="
          width: 4px;
          height: 28px;
          background: ${color};
          border-radius: 2px;
        "></div>
        <div style="flex: 1;">
          <div style="font-weight: 600; font-size: 14px;">${b.label}</div>
          <div class="muted" style="font-size: 12px;">
            ${duration} • ${targetDisplay}
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function buildDailyDebrief(rec, review) {
  const sleep = rec?.sleep_score;
  const hrv = rec?.hrv;
  const workoutDone = review?.execution?.status === 'ok';
  const workoutName = review?.execution?.activity?.name || review?.prescription?.workout_title || 'session';
  const match = review?.analysis?.interval_matching;

  if (typeof sleep === 'number' && sleep >= 85 && workoutDone) {
    if (match === 'matched' || match === 'partial') {
      return `You slept well overnight despite yesterday's ${workoutName}. Recovery signals look strong for today.`;
    }
    return `You slept well overnight after yesterday's ${workoutName}. Recovery looks solid heading into today.`;
  }

  if (typeof sleep === 'number' && sleep < 75) {
    return `Sleep came in lower last night. Keep today's load controlled and prioritize recovery habits.`;
  }

  if (typeof hrv === 'number' && hrv >= 95) {
    return `HRV is strong this morning, suggesting good readiness even if yesterday was demanding.`;
  }

  if (workoutDone) {
    return `You completed yesterday's ${workoutName}. Today looks like a steady progression day.`;
  }

  return `Recovery signals are in. Use today's recommendation and check in after training so we can adapt tomorrow.`;
}

function renderRecovery(p, review, llmDebrief) {
  const r = p.screens.recovery_load || {};
  const m = p.screens.morning_brief || {};
  const rec = r.recovery || {};
  const load = r.load || {};
  const act = r.activity_summary || {};
  const sleepHours = rec.sleep_seconds ? (rec.sleep_seconds / 3600).toFixed(1) : '—';
  
  // Use LLM debrief if available, otherwise fallback to deterministic
  const debrief = llmDebrief 
    ? `<div style="font-weight: 600; margin-bottom: 8px;">${llmDebrief.headline}</div><div>${llmDebrief.debrief}</div><div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border); font-weight: 500;">Today's Focus: ${llmDebrief.today_focus}</div>`
    : buildDailyDebrief(rec, review);
  
  const freshStatus = m.headline?.fresh ? '✅ Fresh' : '⚠️ Stale';
  const freshMins = m.headline?.freshness_age_minutes ?? '—';

  return `
    <div class="card">
      <div class="label">Daily Debrief</div>
      <div style="font-size: 16px; line-height: 1.5; color: var(--text-secondary); margin-top: 8px;">${debrief}</div>
      <div class="muted" style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border);">
        Data: ${freshStatus} • Updated ${freshMins} min ago
      </div>
    </div>
    
    <div class="card">
      <div class="label">Recovery Metrics</div>
      <div class="row">
        ${card('Sleep Score', rec.sleep_score ?? '—')}
        ${card('Sleep Hours', sleepHours)}
        ${card('HRV', rec.hrv ?? '—')}
        ${card('Resting HR', rec.resting_hr ?? '—')}
      </div>
      ${rec.weight_kg ? `<div class="row">
        ${card('Weight (kg)', rec.weight_kg)}
      </div>` : ''}
    </div>
    
    <div class="card">
      <div class="label">Training Load</div>
      <div class="row">
        ${card('CTL', load.ctl ?? '—')}
        ${card('ATL', load.atl ?? '—')}
        ${card('Daily TL', load.daily_training_load ?? '—')}
        ${card('Ramp Rate', load.ramp_rate ?? '—')}
      </div>
    </div>
    
    ${act.count ? `<div class="card">
      <div class="label">Recent Activity Summary</div>
      <div class="row">
        ${card('Workouts', act.count)}
        ${card('Total kJ', act.total_kj ?? '—')}
        ${card('Total Calories', act.total_calories ?? '—')}
        ${card('Avg NP', act.avg_np ?? '—')}
      </div>
    </div>` : ''}
  `;
}

function renderTodayWorkout(modalities, recommendation, llmExplanation) {
  const options = modalities
    .map((m) => `<option value="${m}" ${m === recommendation.selected_sport ? 'selected' : ''}>${m}</option>`)
    .join('');

  const workoutBlocks = recommendation.plan?.blocks || [];
  const workoutGraph = renderWorkoutGraph(workoutBlocks);
  const workoutDetails = renderWorkoutBlocks(workoutBlocks);

  const fb = getAthleteFeedback();
  const coachMode = getCoachMode();
  const advanced = isAdvancedUi();

  return `
    <div class="card">
      ${advanced ? `<div class="label">Athlete ID</div>
      <div style="display: flex; gap: 8px; margin-bottom: 16px;">
        <input id="athleteIdInput" value="${getAthleteId()}" placeholder="athlete id" style="flex: 1;" />
        <button id="applyAthleteBtn">Load</button>
      </div>` : ''}
      <div class="label">Today's Activity</div>
      <div style="display: flex; gap: 8px; align-items: center; margin: 8px 0 16px 0;">
        <select id="sportSelect" style="flex: 1;">${options}</select>
        <button id="applySportBtn">Apply</button>
      </div>
      <div style="margin-bottom: 16px;">
        <label class="muted" style="display: flex; align-items: center; gap: 6px;">
          <input id="coachModeToggle" type="checkbox" ${coachMode ? 'checked' : ''}/> 
          Coach Mode (TP-first)
        </label>
      </div>
      <div style="margin-bottom: 16px;">
        <div class="label" style="margin-bottom: 8px;">How did yesterday feel?</div>
        <div style="display: flex; gap: 8px;">
          <button id="fbEasyBtn" style="flex: 1;" ${fb === 'easy' ? 'disabled' : ''}>Too Easy</button>
          <button id="fbOkBtn" style="flex: 1;" ${fb === 'ok' ? 'disabled' : ''}>About Right</button>
          <button id="fbHardBtn" style="flex: 1;" ${fb === 'hard' ? 'disabled' : ''}>Too Hard</button>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="label">Recommended Session</div>
      <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
        <div class="value">${recommendation.plan?.title || '—'}</div>
        <div style="
          background: ${recommendation.intensity_band === 'easy' ? '#4a9eff' : recommendation.intensity_band === 'moderate' ? '#10b981' : '#ef4444'};
          color: white;
          padding: 4px 12px;
          border-radius: 12px;
          font-size: 12px;
          font-weight: 600;
          text-transform: capitalize;
        ">${recommendation.intensity_band || 'moderate'}</div>
      </div>
      ${advanced ? `<div class="muted" style="margin-bottom: 8px;">sport: ${recommendation.plan?.sport_type || '—'} • schema: ${recommendation.plan?.schema_version || '—'}</div>` : ''}
      ${workoutBlocks.length > 0 ? `${workoutGraph}<div style="margin-top: 8px;">${workoutDetails}</div>` : '<div class="muted">No interval structure available</div>'}
    </div>

    <div class="card">
      <div class="label">Why This Workout</div>
      <div class="muted" style="line-height: 1.6;">${llmExplanation || recommendation.coach_explanation?.summary || 'Adaptive recommendation based on load, recovery, and feedback.'}</div>
      ${advanced && recommendation.coach_explanation?.recommended_overlay ? `
        <div class="muted" style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border);">
          Overlay: ${recommendation.coach_explanation.recommended_overlay.next_action} • ${recommendation.coach_explanation.recommended_overlay.modification_reason}
        </div>` : ''}
      ${advanced ? `<div class="muted" style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border);">
        Mode: ${recommendation.athlete_mode} • Intensity: ${recommendation.intensity_band} • Next: ${recommendation.next_action}
        <br>Reason: ${recommendation.modification_reason}
      </div>` : ''}
    </div>
  `;
}

function renderWorkout(w) {
  const presc = w.prescription;
  const exec = w.execution;
  const analysis = w.analysis;

  const prescStatus = presc.status === 'ok' ? '✅ Available' : '⚠️ Unavailable';
  const execStatus = exec.status === 'ok' ? '✅ Completed' : '⚠️ Not done';
  
  const matchIcon = analysis.interval_matching === 'matched' ? '✅' : 
                     analysis.interval_matching === 'partial' ? '⚠️' : 
                     analysis.interval_matching === 'mismatch' ? '❌' : '—';

  let content = `
    <div class="card">
      <div class="label">Workout Date</div>
      <div class="value" style="margin-bottom: 16px;">${w.date}</div>
      
      <div class="row">
        ${card('Prescription', prescStatus)}
        ${card('Execution', execStatus)}
      </div>
      
      <div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border-subtle);">
        <div class="row">
          ${card('Match Quality', `${matchIcon} ${analysis.interval_matching || '—'}`)}
          ${card('Score', analysis.score ?? '—')}
        </div>
        <div class="row">
          ${card('Confidence', analysis.confidence || '—')}
          ${card('Tier', analysis.matching_tier || '—')}
        </div>
      </div>
    </div>
  `;

  if (presc.status === 'ok') {
    content += `<div class="card">
      <div class="label">Planned Workout</div>
      <div class="value" style="margin-bottom: 12px;">${presc.workout_title || '—'}</div>
      <div class="row">
        ${card('Planned TSS', presc.planned_tss ?? '—')}
        ${card('Duration (min)', presc.planned_duration_sec ? Math.round(presc.planned_duration_sec / 60) : '—')}
        ${card('Intervals', presc.intervals?.length ?? 0)}
      </div>
    </div>`;
  }

  if (exec.status === 'ok' && exec.activity) {
    const a = exec.activity;
    content += `<div class="card">
      <div class="label">Executed Workout</div>
      <div class="value" style="margin-bottom: 12px;">${a.name || '—'}</div>
      <div class="row">
        ${card('Avg Watts', a.avg_watts ?? '—')}
        ${card('Weighted Avg', a.weighted_avg_watts ?? '—')}
        ${card('Avg HR', a.avg_hr ?? '—')}
        ${card('Training Load', a.training_load ?? '—')}
      </div>
      <div class="row">
        ${card('Intensity', a.intensity ?? '—')}
        ${card('Decoupling %', a.decoupling ? `${a.decoupling}%` : '—')}
      </div>
    </div>`;
  }

  if (analysis.intervals?.length) {
    const intervals = analysis.intervals
      .map((i) => {
        const icon = i.hit ? '✅' : '⚠️';
        return `<div style="padding: 8px 0; border-bottom: 1px solid var(--border-subtle); font-size: 14px;">
          <div style="color: var(--text-primary); margin-bottom: 4px;">${icon} ${i.label}</div>
          <div style="color: var(--text-muted); font-size: 13px;">
            Target: ${i.target_low}-${i.target_high} ${i.target_type} → Executed: ${i.executed}
          </div>
        </div>`;
      })
      .join('');
    content += `<div class="card">
      <div class="label">Interval Matching</div>
      <div style="margin-top: 8px;">${intervals}</div>
    </div>`;
  }

  if (analysis.reason_codes?.length) {
    content += `<div class="card">
      <div class="label">Analysis Notes</div>
      <pre style="margin-top: 8px;">${analysis.reason_codes.join('\n')}</pre>
    </div>`;
  }

  return content;
}

function renderPlan(horizon) {
  const weekDays = (horizon?.days || []).slice(0, 7);
  const coachMode = horizon?.coach_mode || false;
  
  const dayCards = weekDays.map(d => {
    const intensityColor = 
      d.intensity_band === 'easy' ? '#4a9eff' :
      d.intensity_band === 'moderate' ? '#10b981' :
      d.intensity_band === 'hard' ? '#ef4444' : '#6b7690';
    
    // Parse date correctly (YYYY-MM-DD as local date, not UTC)
    const dateParts = d.date.split('-');
    const localDate = new Date(parseInt(dateParts[0]), parseInt(dateParts[1]) - 1, parseInt(dateParts[2]));
    
    // Multi-workout support: show primary workout + additional same-day sessions
    const dayWorkouts = (d.planned_workouts && d.planned_workouts.length) ? d.planned_workouts : [d.plan || d.planned_workout].filter(Boolean);
    const primaryWorkout = d.plan || d.planned_workout || dayWorkouts[0] || {};
    const workoutTitle = primaryWorkout?.title || `${d.sport_type} session`;
    const workoutBlocks = primaryWorkout?.blocks || [];
    
    // Use duration_hours from plan (authoritative from TP), fallback to blocks
    let durationHours = primaryWorkout?.duration_hours || null;
    if (!durationHours && workoutBlocks.length > 0) {
      const totalSec = workoutBlocks.reduce((sum, b) => sum + (b.duration_sec || 0), 0);
      durationHours = totalSec / 3600;
    }
    const source = d.plan_source || (coachMode ? 'trainingpeaks' : 'generated');
    
    // Render workout blocks if available
    let blocksHtml = '';
    if (workoutBlocks.length > 0) {
      blocksHtml = workoutBlocks.map(b => {
        const blockColor = getBlockColor(b);
        const blockDuration = b.duration_minutes || (b.duration_sec ? Math.round(b.duration_sec / 60) : 0);
        const hasTargets = b.target_low != null && b.target_high != null;
        const targetDisplay = hasTargets 
          ? `${b.target_low}-${b.target_high}% ${formatTargetType(b.target_type)}`
          : b.target_low != null 
            ? `${b.target_low}% ${formatTargetType(b.target_type)}`
            : 'Easy effort';
        
        return `
          <div style="display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 12px;">
            <div style="width: 3px; height: 20px; background: ${blockColor}; border-radius: 2px;"></div>
            <div style="flex: 1;">
              <span style="font-weight: 500;">${b.label || 'Interval'}:</span>
              <span class="muted">${blockDuration}min • ${targetDisplay}</span>
            </div>
          </div>
        `;
      }).join('');
    }
    
    return `
      <div class="card" style="padding: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
          <div style="flex: 1;">
            <div class="label">${localDate.toLocaleDateString('en-US', {weekday: 'short', month: 'short', day: 'numeric'})}</div>
            <div class="value" style="font-size: 14px; margin-top: 4px;">${workoutTitle}</div>
            ${durationHours ? `<div class="muted" style="font-size: 12px; margin-top: 2px;">${durationHours.toFixed(1)}h</div>` : ''}
          </div>
          <div style="
            background: ${intensityColor};
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            text-transform: capitalize;
          ">${d.intensity_band}</div>
        </div>
        
        ${blocksHtml ? `
          <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border, #1a1f2e);">
            ${blocksHtml}
          </div>
        ` : ''}

        ${dayWorkouts.length > 1 ? `
          <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border, #1a1f2e);">
            <div class="label" style="font-size: 11px; margin-bottom: 8px;">Additional Workouts (${dayWorkouts.length - 1})</div>
            ${dayWorkouts.slice(1).map(w => {
              const dHours = w?.duration_hours ? `${w.duration_hours.toFixed(1)}h` : '';
              const s = (w?.sport_type || 'session').toString();
              return `<div style="font-size: 12px; color: var(--text-muted); padding: 4px 0;">
                • <span style="color: var(--text-primary);">${w?.title || 'Workout'}</span>
                <span style="text-transform: capitalize;">(${s})</span>
                ${dHours ? `• ${dHours}` : ''}
              </div>`;
            }).join('')}
          </div>
        ` : ''}
        
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 12px; font-size: 11px;">
          <span class="muted">${source === 'trainingpeaks' ? '📋 TrainingPeaks' : source === 'generated' ? '🤖 AI Generated' : '💭 Planned'}</span>
          <span class="muted">${d.firm ? '📌 Firm' : '💭 Soft'}</span>
        </div>
      </div>
    `;
  }).join('');

  const advanced = isAdvancedUi();

  return `
    <div class="card">
      <div class="label">Training Phase</div>
      <div class="value" style="font-size: 16px; margin-top: 8px; text-transform: capitalize;">
        ${horizon?.periodization?.phase || '—'}
      </div>
      <div class="muted" style="margin-top: 6px;">${horizon?.periodization?.reason || 'Planning next week...'}</div>
      <div class="muted" style="margin-top: 8px; font-size: 12px;">
        ${horizon?.periodization?.days_to_race != null ? `🏁 ${horizon.periodization.days_to_race} days to race` : '🏁 No race date set'}
        ${horizon?.periodization?.block_periodization?.enabled ? ` • Block week ${horizon.periodization.block_periodization.current_block_week}/${horizon.periodization.block_periodization.block_weeks}` : ''}
        ${horizon?.periodization?.block_periodization?.progressive_overload_multiplier ? ` • Vol x${horizon.periodization.block_periodization.progressive_overload_multiplier}` : ''}
      </div>
      ${advanced && horizon?.coach_mode ? `
        <div class="muted" style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border);">
          Coach Mode: ON • TP days: ${horizon?.coach_horizon_summary?.tp_days_with_plan || 0}/${horizon?.coach_horizon_summary?.total_days || 7}
        </div>
      ` : ''}
    </div>

    <div style="display: grid; gap: 12px;">
      ${dayCards || '<div class="card"><div class="muted">No plan data available</div></div>'}
    </div>
  `;
}

function renderAnalysis(data, workoutData) {
  if (!data || !data.insights) {
    return `
      <div class="card">
        <div class="label">Analysis Insights</div>
        <div class="muted">Loading analysis...</div>
      </div>
    `;
  }

  const insights = data.insights;
  const cached = data.cached || false;
  const generatedAt = data.generated_at ? new Date(data.generated_at) : null;
  const timeAgo = generatedAt ? formatTimeAgo(generatedAt) : '';

  const performance = (insights.performance_insights || []).map(i => 
    `<li>${i}</li>`
  ).join('');
  
  const recovery = (insights.recovery_insights || []).map(i => 
    `<li>${i}</li>`
  ).join('');
  
  const recommendations = (insights.recommendations || []).map(i => 
    `<li>${i}</li>`
  ).join('');
  
  // Today's workout analysis section
  let workoutSection = '';
  if (workoutData && workoutData.analysis) {
    const wa = workoutData.analysis;
    const completed = wa.completed !== false;
    
    if (completed) {
      const adherenceColor = 
        wa.adherence === 'excellent' ? '#10b981' :
        wa.adherence === 'good' ? '#4a9eff' :
        wa.adherence === 'partial' ? '#f59e0b' : '#ef4444';
      
      const qualityColor =
        wa.execution_quality === 'excellent' ? '#10b981' :
        wa.execution_quality === 'good' ? '#4a9eff' :
        wa.execution_quality === 'average' ? '#f59e0b' : '#ef4444';
      
      const waInsights = (wa.insights || []).map(i => `<li>${i}</li>`).join('');
      const waRecs = (wa.recommendations || []).map(i => `<li>${i}</li>`).join('');
      
      workoutSection = `
        <div class="card">
          <div class="label">Today's Workout Analysis</div>
          <div class="value" style="font-size: 16px; margin-top: 8px;">${wa.summary || 'Workout completed'}</div>
          
          <div style="display: flex; gap: 12px; margin-top: 16px;">
            <div style="flex: 1;">
              <div class="muted" style="font-size: 12px; margin-bottom: 4px;">Adherence</div>
              <div style="
                display: inline-block;
                padding: 6px 12px;
                background: ${adherenceColor};
                color: white;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
                text-transform: capitalize;
              ">${wa.adherence || 'unknown'}</div>
            </div>
            
            ${wa.execution_quality ? `
              <div style="flex: 1;">
                <div class="muted" style="font-size: 12px; margin-bottom: 4px;">Execution Quality</div>
                <div style="
                  display: inline-block;
                  padding: 6px 12px;
                  background: ${qualityColor};
                  color: white;
                  border-radius: 6px;
                  font-size: 13px;
                  font-weight: 600;
                  text-transform: capitalize;
                ">${wa.execution_quality.replace('_', ' ')}</div>
              </div>
            ` : ''}
          </div>
          
          ${waInsights ? `
            <div style="margin-top: 16px;">
              <div class="muted" style="font-size: 12px; margin-bottom: 8px; font-weight: 600;">Insights</div>
              <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
                ${waInsights}
              </ul>
            </div>
          ` : ''}
          
          ${waRecs ? `
            <div style="margin-top: 12px;">
              <div class="muted" style="font-size: 12px; margin-bottom: 8px; font-weight: 600;">Recommendations</div>
              <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
                ${waRecs}
              </ul>
            </div>
          ` : ''}
        </div>
      `;
    } else {
      workoutSection = `
        <div class="card">
          <div class="label">Today's Workout Analysis</div>
          <div class="muted" style="padding: 20px;">No workout completed today yet.</div>
        </div>
      `;
    }
  }

  return `
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
          <div class="label">Analysis</div>
          ${generatedAt ? `<div class="muted" style="font-size: 12px; margin-top: 4px;">
            ${cached ? '💾 Cached' : '✨ Fresh'} • Generated ${timeAgo}
          </div>` : ''}
        </div>
        <button id="refreshAnalysisBtn" style="
          background: var(--accent, #4a9eff);
          color: white;
          border: none;
          padding: 8px 16px;
          border-radius: 8px;
          font-size: 12px;
          font-weight: 600;
          cursor: pointer;
          white-space: nowrap;
        ">Refresh</button>
      </div>
    </div>
    
    ${workoutSection}
    
    <div class="card">
      <div class="label">14-Day Analysis</div>
      <div class="value" style="font-size: 16px; margin-top: 8px;">${insights.summary || 'Analysis complete'}</div>
    </div>

    <div class="card">
      <div class="label">Performance Insights</div>
      <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
        ${performance || '<li class="muted">No performance data available</li>'}
      </ul>
    </div>

    <div class="card">
      <div class="label">Recovery Insights</div>
      <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
        ${recovery || '<li class="muted">No recovery data available</li>'}
      </ul>
    </div>

    <div class="card">
      <div class="label">Recommendations</div>
      <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
        ${recommendations || '<li class="muted">No recommendations available</li>'}
      </ul>
    </div>
  `;
}

function formatTimeAgo(date) {
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}min ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

function attachAnalysisHandlers() {
  const refreshBtn = document.getElementById('refreshAnalysisBtn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
      refreshBtn.disabled = true;
      refreshBtn.textContent = 'Refreshing...';
      try {
        const data = await fetchLLMAnalysis(true);  // force refresh 14-day analysis
        const workoutData = await fetchTodaysWorkoutAnalysis();  // workout analysis cached per day
        const app = document.getElementById('app');
        app.innerHTML = renderAnalysis(data, workoutData);
        attachAnalysisHandlers();  // re-attach after re-render
      } catch (e) {
        alert(e.message || 'Refresh failed. Please try again in 6 hours.');
        refreshBtn.disabled = false;
        refreshBtn.textContent = 'Refresh';
      }
    });
  }
}

function renderChat(messages = []) {
  const messagesHtml = messages.length > 0
    ? messages.map(m => `
        <div style="margin-bottom: 16px;">
          <div style="font-size: 12px; color: var(--muted); margin-bottom: 4px; font-weight: 600;">
            ${m.role === 'user' ? 'You' : 'PeakFlow'}
          </div>
          <div style="padding: 12px; background: ${m.role === 'user' ? 'var(--card)' : 'var(--accent-dim, #1a2942)'}; border-radius: 12px; line-height: 1.6;">
            ${m.content}
          </div>
        </div>
      `).join('')
    : '<div class="muted" style="text-align: center; padding: 40px 20px;">Ask me anything about your training, recovery, or how to use PeakFlow!</div>';
  
  return `
    <div class="card">
      <div class="label">Chat with PeakFlow</div>
      <div style="max-height: 400px; overflow-y: auto; margin-bottom: 16px;" id="chatMessages">
        ${messagesHtml}
      </div>
      <div style="display: flex; gap: 8px;">
        <input
          type="text"
          id="chatInput"
          placeholder="Ask about training, recovery, or app features..."
          style="flex: 1; padding: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--card); color: var(--text);"
        />
        <button id="chatSendBtn" style="padding: 12px 24px; background: var(--accent); color: white; border: none; border-radius: 8px; font-weight: 600; cursor: pointer;">
          Send
        </button>
      </div>
    </div>
  `;
}

function renderPreferences(prefs = {}) {
  const sports = prefs.sports || ['cycling'];
  const weeklyHours = prefs.weekly_hours || 10;
  const goals = prefs.goals || '';
  const heightCm = prefs.height_cm || '';
  const weightKg = prefs.weight_kg || '';
  const units = prefs.units || 'imperial';
  const raceDates = (prefs.race_dates || []).join(', ');
  const blockWeeks = prefs.block_weeks || 4;
  
  // Convert for display if imperial
  const heightDisplay = units === 'imperial' && heightCm ? (heightCm / 2.54).toFixed(1) : heightCm;
  const weightDisplay = units === 'imperial' && weightKg ? (weightKg * 2.20462).toFixed(1) : weightKg;
  
  const heightLabel = units === 'imperial' ? 'Height (in)' : 'Height (cm)';
  const weightLabel = units === 'imperial' ? 'Weight (lbs)' : 'Weight (kg)';
  const heightPlaceholder = units === 'imperial' ? '69' : '175';
  const weightPlaceholder = units === 'imperial' ? '154' : '70';
  
  return `
    <div class="card">
      <div class="label">Your Preferences</div>
      
      <div style="margin-top: 20px;">
        <label style="display: block; margin-bottom: 8px; font-weight: 600;">Units</label>
        <div style="display: flex; gap: 12px; margin-bottom: 20px;">
          <label style="display: flex; align-items: center; gap: 6px; padding: 10px 16px; background: ${units === 'imperial' ? 'var(--accent)' : 'var(--card)'}; color: ${units === 'imperial' ? 'white' : 'var(--text)'}; border: 1px solid ${units === 'imperial' ? 'var(--accent)' : 'var(--border)'}; border-radius: 8px; cursor: pointer;">
            <input type="radio" name="units" value="imperial" ${units === 'imperial' ? 'checked' : ''} style="cursor: pointer;" />
            <span>Imperial (lbs, in)</span>
          </label>
          <label style="display: flex; align-items: center; gap: 6px; padding: 10px 16px; background: ${units === 'metric' ? 'var(--accent)' : 'var(--card)'}; color: ${units === 'metric' ? 'white' : 'var(--text)'}; border: 1px solid ${units === 'metric' ? 'var(--accent)' : 'var(--border)'}; border-radius: 8px; cursor: pointer;">
            <input type="radio" name="units" value="metric" ${units === 'metric' ? 'checked' : ''} style="cursor: pointer;" />
            <span>Metric (kg, cm)</span>
          </label>
        </div>
        
        <label style="display: block; margin-bottom: 8px; font-weight: 600;">Sports</label>
        <div style="display: flex; flex-wrap: gap; gap: 8px; margin-bottom: 16px;">
          ${['cycling', 'running', 'hiking', 'strength', 'yoga', 'swimming'].map(s => `
            <label style="display: flex; align-items: center; gap: 6px; padding: 8px 12px; background: var(--card); border: 1px solid var(--border); border-radius: 8px; cursor: pointer;">
              <input type="checkbox" name="sport" value="${s}" ${sports.includes(s) ? 'checked' : ''} style="cursor: pointer;" />
              <span style="text-transform: capitalize;">${s}</span>
            </label>
          `).join('')}
        </div>
        
        <label style="display: block; margin-bottom: 8px; font-weight: 600;">Weekly Hours Target</label>
        <input
          type="number"
          id="weeklyHoursInput"
          value="${weeklyHours}"
          min="1"
          max="50"
          step="0.5"
          style="width: 100%; padding: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--card); color: var(--text); margin-bottom: 16px;"
        />
        
        <label style="display: block; margin-bottom: 8px; font-weight: 600;">Goals & Focus Areas</label>
        <textarea
          id="goalsInput"
          placeholder="e.g., Build endurance for summer crits, improve climbing power"
          style="width: 100%; padding: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--card); color: var(--text); min-height: 80px; resize: vertical; margin-bottom: 16px; font-family: inherit;"
        >${goals}</textarea>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">
          <div>
            <label style="display: block; margin-bottom: 8px; font-weight: 600;">${heightLabel}</label>
            <input
              type="number"
              id="heightInput"
              value="${heightDisplay}"
              placeholder="${heightPlaceholder}"
              min="${units === 'imperial' ? '39' : '100'}"
              max="${units === 'imperial' ? '98' : '250'}"
              step="${units === 'imperial' ? '0.5' : '1'}"
              style="width: 100%; padding: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--card); color: var(--text);"
            />
          </div>
          <div>
            <label style="display: block; margin-bottom: 8px; font-weight: 600;">${weightLabel}</label>
            <input
              type="number"
              id="weightInput"
              value="${weightDisplay}"
              placeholder="${weightPlaceholder}"
              min="${units === 'imperial' ? '66' : '30'}"
              max="${units === 'imperial' ? '440' : '200'}"
              step="0.1"
              style="width: 100%; padding: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--card); color: var(--text);"
            />
          </div>
        </div>

        <label style="display: block; margin-bottom: 8px; font-weight: 600;">Race Dates (optional)</label>
        <input
          type="text"
          id="raceDatesInput"
          value="${raceDates}"
          placeholder="YYYY-MM-DD, YYYY-MM-DD"
          style="width: 100%; padding: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--card); color: var(--text); margin-bottom: 8px;"
        />
        <div class="muted" style="font-size: 12px; margin-bottom: 16px;">Comma-separated dates. Used for taper/peak planning.</div>

        <label style="display: block; margin-bottom: 8px; font-weight: 600;">Block Periodization Cycle (weeks)</label>
        <input
          type="number"
          id="blockWeeksInput"
          value="${blockWeeks}"
          min="3"
          max="6"
          step="1"
          style="width: 100%; padding: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--card); color: var(--text); margin-bottom: 16px;"
        />
        
        <button id="savePreferencesBtn" style="width: 100%; padding: 14px; background: var(--accent); color: white; border: none; border-radius: 8px; font-weight: 600; font-size: 16px; cursor: pointer;">
          Save Preferences
        </button>
      </div>
    </div>
  `;
}

function attachTodayWorkoutHandlers() {
  const athleteInput = document.getElementById('athleteIdInput');
  const athleteBtn = document.getElementById('applyAthleteBtn');
  const select = document.getElementById('sportSelect');
  const btn = document.getElementById('applySportBtn');
  const coachToggle = document.getElementById('coachModeToggle');
  const fbEasy = document.getElementById('fbEasyBtn');
  const fbOk = document.getElementById('fbOkBtn');
  const fbHard = document.getElementById('fbHardBtn');
  const relBtns = [1, 2, 3, 4, 5].map((n) => document.getElementById(`rel${n}Btn`));
  if (athleteInput && athleteBtn) {
    athleteBtn.addEventListener('click', async () => {
      setAthleteId(athleteInput.value || 'default');
      await render();
    });
  }
  if (select && btn) {
    btn.addEventListener('click', async () => {
      setSelectedSport(select.value);
      await render();
    });
  }
  if (coachToggle) {
    coachToggle.addEventListener('change', async () => {
      setCoachMode(coachToggle.checked);
      await render();
    });
  }
  if (fbEasy) fbEasy.addEventListener('click', async () => { setAthleteFeedback('easy'); await render(); });
  if (fbOk) fbOk.addEventListener('click', async () => { setAthleteFeedback('ok'); await render(); });
  if (fbHard) fbHard.addEventListener('click', async () => { setAthleteFeedback('hard'); await render(); });

  relBtns.forEach((btn, idx) => {
    if (!btn) return;
    btn.addEventListener('click', async () => {
      try {
        await logRecommendationFeedback({
          athleteId: getAthleteId(),
          relevance: idx + 1,
          perceived: getAthleteFeedback() || 'unspecified',
          recId: `${Date.now()}`,
        });
      } catch (_) {
        // keep UX smooth even if telemetry log fails
      }
    });
  });
}

function getYesterdayISO() {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d.toISOString().slice(0, 10);
}

function routeName() {
  return (location.hash || '#/').replace('#', '');
}

function setAuthStatus(text) {
  const el = document.getElementById('authStatus');
  if (el) el.textContent = text;
}

function syncAdvancedUi() {
  const panel = document.getElementById('advancedPanel');
  const btn = document.getElementById('advancedToggleBtn');
  const on = isAdvancedUi();
  if (panel) panel.classList.toggle('hidden', !on);
  if (btn) btn.textContent = on ? 'Hide Advanced' : 'Advanced';
}

async function refreshAuthStatus() {
  const r = await apiGet('/api/health');
  if (r.ok) setAuthStatus(`Auth: connected (${getToken() ? 'token set' : 'open'})`);
  else if (r.status === 401) setAuthStatus('Auth: unauthorized (set token)');
  else setAuthStatus(`Auth: error (${r.status})`);
}

async function render() {
  const app = document.getElementById('app');
  try {
    const r = routeName();
    if (r === '/workout') {
      // Today's Workout = recommendation view
      const athleteId = getAthleteId();
      const serverState = await fetchPlannerState(athleteId);

      const selected = localStorage.getItem(SPORT_KEY) ? getSelectedSport() : (serverState.selected_sport || getSelectedSport());
      const focus = localStorage.getItem(FOCUS_SPORT_KEY) ? getFocusSport() : (serverState.focus_sport || getFocusSport());
      const athleteFeedback = localStorage.getItem(ATHLETE_FEEDBACK_KEY) ? getAthleteFeedback() : (serverState.athlete_feedback || getAthleteFeedback());
      const coachMode = localStorage.getItem(COACH_MODE_KEY) ? getCoachMode() : ((typeof serverState.coach_mode === 'boolean') ? serverState.coach_mode : getCoachMode());

      // keep local cache aligned for UI continuity
      setSelectedSport(selected);
      if (focus) setFocusSport(focus);
      if (athleteFeedback) setAthleteFeedback(athleteFeedback);
      setCoachMode(coachMode);

      const [modalities, recommendation, llmExplanation] = await Promise.all([
        fetchModalities(),
        fetchPlanRecommendation(selected, focus, athleteFeedback, coachMode, athleteId),
        fetchLLMWorkoutExplanation(selected, athleteId, coachMode),
      ]);
      app.innerHTML = renderTodayWorkout(modalities, recommendation, llmExplanation);
      attachTodayWorkoutHandlers();
    } else if (r === '/plan') {
      // Plan = 7-day calendar view
      const athleteId = getAthleteId();
      const serverState = await fetchPlannerState(athleteId);
      
      const selected = localStorage.getItem(SPORT_KEY) ? getSelectedSport() : (serverState.selected_sport || getSelectedSport());
      const focus = localStorage.getItem(FOCUS_SPORT_KEY) ? getFocusSport() : (serverState.focus_sport || getFocusSport());
      const coachMode = localStorage.getItem(COACH_MODE_KEY) ? getCoachMode() : ((typeof serverState.coach_mode === 'boolean') ? serverState.coach_mode : getCoachMode());

      const horizon = await fetchPlanHorizon(selected, focus, athleteId, coachMode);
      app.innerHTML = renderPlan(horizon);
    } else if (r === '/analysis') {
      // Analysis = performance and recovery trend insights + today's workout
      const data = await fetchLLMAnalysis();
      const workoutData = await fetchTodaysWorkoutAnalysis();
      app.innerHTML = renderAnalysis(data, workoutData);
      attachAnalysisHandlers();
    } else if (r === '/preferences') {
      // Preferences page
      const prefs = await fetchPreferences();
      app.innerHTML = renderPreferences(prefs);
      attachPreferencesHandlers();
    } else if (r === '/chat') {
      // Chat = conversational interface
      const chatHistory = JSON.parse(localStorage.getItem('peakflow_chat_history') || '[]');
      app.innerHTML = renderChat(chatHistory);
      attachChatHandlers();
    } else {
      // Default to recovery view for / and /recovery
      const payload = await fetchPayload();
      const yesterdayReview = await fetchWorkoutReview(getYesterdayISO());
      const llmDebrief = await fetchLLMDebrief();
      app.innerHTML = renderRecovery(payload, yesterdayReview, llmDebrief);
    }
  } catch (e) {
    app.innerHTML = `<div class='card'>Error: ${e.message}</div>`;
  }
  await refreshAuthStatus();
}

function initAuthUi() {
  const tokenInput = document.getElementById('tokenInput');
  const saveBtn = document.getElementById('saveTokenBtn');
  const clearBtn = document.getElementById('clearTokenBtn');
  const advancedToggleBtn = document.getElementById('advancedToggleBtn');

  if (tokenInput) tokenInput.value = getToken();

  if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
      setToken(tokenInput?.value || '');
      await render();
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', async () => {
      setToken('');
      if (tokenInput) tokenInput.value = '';
      await render();
    });
  }

  if (advancedToggleBtn) {
    advancedToggleBtn.addEventListener('click', () => {
      setAdvancedUi(!isAdvancedUi());
      syncAdvancedUi();
      render();
    });
  }

  syncAdvancedUi();
}

function attachPreferencesHandlers() {
  const saveBtn = document.getElementById('savePreferencesBtn');
  const unitsRadios = document.querySelectorAll('input[name="units"]');
  
  // Re-render when units change to update labels/values
  unitsRadios.forEach(radio => {
    radio.addEventListener('change', async () => {
      const prefs = await fetchPreferences();
      const app = document.getElementById('app');
      app.innerHTML = renderPreferences(prefs);
      attachPreferencesHandlers();
    });
  });
  
  if (!saveBtn) return;
  
  saveBtn.addEventListener('click', async () => {
    const sportCheckboxes = document.querySelectorAll('input[name="sport"]:checked');
    const sports = Array.from(sportCheckboxes).map(cb => cb.value);
    const weeklyHours = parseFloat(document.getElementById('weeklyHoursInput').value);
    const goals = document.getElementById('goalsInput').value.trim();
    const units = document.querySelector('input[name="units"]:checked').value;
    
    // Get height/weight values (convert to metric if imperial)
    let heightCm = null;
    let weightKg = null;
    
    const heightInput = document.getElementById('heightInput').value;
    const weightInput = document.getElementById('weightInput').value;
    
    if (heightInput) {
      const heightValue = parseFloat(heightInput);
      heightCm = units === 'imperial' ? heightValue * 2.54 : heightValue;
    }
    
    if (weightInput) {
      const weightValue = parseFloat(weightInput);
      weightKg = units === 'imperial' ? weightValue / 2.20462 : weightValue;
    }
    
    const raceDatesRaw = (document.getElementById('raceDatesInput')?.value || '').trim();
    const raceDates = raceDatesRaw
      ? raceDatesRaw.split(',').map(s => s.trim()).filter(Boolean)
      : [];

    const blockWeeksVal = parseInt(document.getElementById('blockWeeksInput')?.value || '4', 10);
    const blockWeeks = Number.isFinite(blockWeeksVal) ? blockWeeksVal : 4;

    const prefs = {
      sports,
      weekly_hours: weeklyHours,
      goals,
      height_cm: heightCm,
      weight_kg: weightKg,
      units,
      race_dates: raceDates,
      block_weeks: blockWeeks,
    };
    
    saveBtn.textContent = 'Saving...';
    saveBtn.disabled = true;
    
    const success = await savePreferences(prefs);
    
    if (success) {
      saveBtn.textContent = 'Saved!';
      setTimeout(() => {
        saveBtn.textContent = 'Save Preferences';
        saveBtn.disabled = false;
      }, 2000);
    } else {
      saveBtn.textContent = 'Failed to save';
      saveBtn.disabled = false;
    }
  });
}

function attachChatHandlers() {
  const input = document.getElementById('chatInput');
  const sendBtn = document.getElementById('chatSendBtn');
  
  if (!input || !sendBtn) return;
  
  const send = async () => {
    const message = input.value.trim();
    if (!message) return;
    
    input.disabled = true;
    sendBtn.disabled = true;
    sendBtn.textContent = 'Sending...';
    
    // Get current history
    const history = JSON.parse(localStorage.getItem('peakflow_chat_history') || '[]');
    
    // Add user message
    history.push({ role: 'user', content: message });
    localStorage.setItem('peakflow_chat_history', JSON.stringify(history));
    
    // Re-render with user message
    const app = document.getElementById('app');
    app.innerHTML = renderChat(history);
    attachChatHandlers();
    
    try {
      // Send to API
      const response = await sendChatMessage(message);
      
      // Add assistant response
      history.push({ role: 'assistant', content: response });
      localStorage.setItem('peakflow_chat_history', JSON.stringify(history));
      
      // Re-render with response
      app.innerHTML = renderChat(history);
      attachChatHandlers();
      
      // Scroll to bottom
      const messagesEl = document.getElementById('chatMessages');
      if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
      
    } catch (e) {
      history.push({ role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' });
      localStorage.setItem('peakflow_chat_history', JSON.stringify(history));
      app.innerHTML = renderChat(history);
      attachChatHandlers();
    }
  };
  
  sendBtn.addEventListener('click', send);
  input.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') send();
  });
}

window.addEventListener('hashchange', render);
initAuthUi();
render();
