const TOKEN_KEY = 'peakflow_alpha_token';

function getToken() {
  return localStorage.getItem(TOKEN_KEY) || '';
}

function setToken(token) {
  if (!token) localStorage.removeItem(TOKEN_KEY);
  else localStorage.setItem(TOKEN_KEY, token.trim());
}

async function apiGet(path) {
  const token = getToken();
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(path, { headers });
  const body = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, body };
}

async function fetchPayload() {
  const r = await apiGet('/api/alpha/shell/today');
  if (!r.ok) throw new Error(r.body.error || `http_${r.status}`);
  return r.body.payload;
}

async function fetchWorkoutReview() {
  const r = await apiGet('/api/alpha/workout/latest');
  if (!r.ok) throw new Error(r.body.error || `http_${r.status}`);
  return r.body.payload;
}

const SPORT_KEY = 'peakflow_selected_sport';
const FOCUS_SPORT_KEY = 'peakflow_focus_sport';
const ATHLETE_FEEDBACK_KEY = 'peakflow_athlete_feedback';
const COACH_MODE_KEY = 'peakflow_coach_mode';
const ATHLETE_ID = 'default';

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

async function fetchModalities() {
  const r = await apiGet('/api/alpha/planner/modalities');
  if (!r.ok) throw new Error(r.body.error || `http_${r.status}`);
  return r.body.modalities || [];
}

async function fetchPlanRecommendation(sport, focusSport, athleteFeedback, coachMode) {
  const qs = new URLSearchParams({ sport: sport || 'cycling', focusSport: focusSport || '', athleteId: ATHLETE_ID });
  if (athleteFeedback) qs.set('athleteFeedback', athleteFeedback);
  if (coachMode) qs.set('coachMode', 'true');
  const r = await apiGet(`/api/alpha/planner/recommendation?${qs.toString()}`);
  if (!r.ok) throw new Error(r.body.error || `http_${r.status}`);
  return r.body.payload;
}

async function fetchPlanHorizon(sport, focusSport) {
  const qs = new URLSearchParams({ sport: sport || 'cycling', focusSport: focusSport || '', athleteId: ATHLETE_ID });
  if (getCoachMode()) qs.set('coachMode', 'true');
  const r = await apiGet(`/api/alpha/planner/horizon?${qs.toString()}`);
  if (!r.ok) throw new Error(r.body.error || `http_${r.status}`);
  return r.body.payload;
}

function card(label, value) {
  return `<div class="card"><div class="label">${label}</div><div class="value">${value ?? '—'}</div></div>`;
}

function renderMorning(p) {
  const m = p.screens.morning_brief;
  return `
    ${card('Freshness', `${m.headline.fresh ? 'Fresh' : 'Stale'} (${m.headline.freshness_age_minutes ?? '—'}m)`)}
    <div class="row">
      ${card('Weight (kg)', m.quick_recovery.weight_kg)}
      ${card('RHR', m.quick_recovery.resting_hr)}
      ${card('HRV', m.quick_recovery.hrv)}
      ${card('Sleep Score', m.quick_recovery.sleep_score)}
    </div>
    <div class="row">
      ${card('CTL', m.quick_load.ctl)}
      ${card('ATL', m.quick_load.atl)}
      ${card('Daily TL', m.quick_load.daily_training_load)}
    </div>
  `;
}

function renderRecovery(p) {
  const r = p.screens.recovery_load;
  return `<div class="card"><pre>${JSON.stringify(r, null, 2)}</pre></div>`;
}

function renderChat(p) {
  const c = p.screens.chat_context;
  return `<div class="card"><pre>${JSON.stringify(c, null, 2)}</pre></div>`;
}

function renderWorkout(w) {
  const presc = w.prescription;
  const exec = w.execution;
  const analysis = w.analysis;

  const prescStatus = presc.status === 'ok' ? '✅ Available' : '⚠️ Unavailable';
  const execStatus = exec.status === 'ok' ? '✅ Completed' : '⚠️ Not done';

  let content = `
    <div class="card">
      <h2>${w.date}</h2>
      <div class="row">
        ${card('Prescription', prescStatus)}
        ${card('Execution', execStatus)}
      </div>
      <div class="row">
        ${card('Match', analysis.interval_matching || '—')}
        ${card('Score', analysis.score ?? '—')}
        ${card('Confidence', analysis.confidence || '—')}
        ${card('Tier', analysis.matching_tier || '—')}
      </div>
    </div>
  `;

  if (presc.status === 'ok') {
    content += `<div class="card">
      <div class="label">Planned Workout</div>
      <div class="value">${presc.workout_title || '—'}</div>
      <div class="row">
        ${card('Planned TSS', presc.planned_tss ?? '—')}
        ${card('Planned Duration (s)', presc.planned_duration_sec ?? '—')}
        ${card('Intervals', presc.intervals?.length ?? 0)}
      </div>
    </div>`;
  }

  if (exec.status === 'ok' && exec.activity) {
    const a = exec.activity;
    content += `<div class="card">
      <div class="label">Executed Workout</div>
      <div class="value">${a.name || '—'}</div>
      <div class="row">
        ${card('Avg Watts', a.avg_watts ?? '—')}
        ${card('Weighted Avg', a.weighted_avg_watts ?? '—')}
        ${card('Avg HR', a.avg_hr ?? '—')}
        ${card('Training Load', a.training_load ?? '—')}
      </div>
      <div class="row">
        ${card('Intensity', a.intensity ?? '—')}
        ${card('Decoupling %', a.decoupling ?? '—')}
      </div>
    </div>`;
  }

  if (analysis.reason_codes?.length) {
    content += `<div class="card">
      <div class="label">Reason Codes</div>
      <pre>${analysis.reason_codes.join('\n')}</pre>
    </div>`;
  }

  if (analysis.intervals?.length) {
    const intervals = analysis.intervals
      .map(
        (i) => `<div style="margin: 4px 0;">${i.label}: ${i.target_low}-${i.target_high} (${i.target_type}) → ${i.executed} ${i.hit ? '✅' : '⚠️'}</div>`
      )
      .join('');
    content += `<div class="card">
      <div class="label">Interval Matching</div>
      ${intervals}
    </div>`;
  }

  return content;
}

function renderPlan(modalities, recommendation, horizon) {
  const options = modalities
    .map((m) => `<option value="${m}" ${m === recommendation.selected_sport ? 'selected' : ''}>${m}</option>`)
    .join('');

  const blocks = (recommendation.plan?.blocks || [])
    .map((b) => `<li>${b.label}: ${b.duration_sec}s • ${b.target_type} ${b.target_low ?? '—'}-${b.target_high ?? '—'}</li>`)
    .join('');

  const weekRows = (horizon?.days || [])
    .slice(0, 7)
    .map((d) => `<li>${d.date} • ${d.intensity_band} • ${d.sport_type} ${d.firm ? '(firm)' : '(soft)'}</li>`)
    .join('');

  const fb = getAthleteFeedback();
  const coachMode = getCoachMode();

  return `
    <div class="card">
      <div class="label">Today's Activity</div>
      <select id="sportSelect">${options}</select>
      <button id="applySportBtn">Apply</button>
      <div style="margin-top:8px;">
        <label class="muted"><input id="coachModeToggle" type="checkbox" ${coachMode ? 'checked' : ''}/> Coach Mode (TP-first)</label>
      </div>
      <div style="margin-top:8px;">
        <span class="muted">How did yesterday feel?</span>
        <button id="fbEasyBtn" ${fb === 'easy' ? 'disabled' : ''}>Too Easy</button>
        <button id="fbOkBtn" ${fb === 'ok' ? 'disabled' : ''}>About Right</button>
        <button id="fbHardBtn" ${fb === 'hard' ? 'disabled' : ''}>Too Hard</button>
      </div>
      <div class="muted">Mode: ${recommendation.athlete_mode} • Intensity: ${recommendation.intensity_band} • Next: ${recommendation.next_action}</div>
      <div class="muted">Reason: ${recommendation.modification_reason}</div>
      <div class="muted">Plan Source: ${recommendation.plan_source || 'peakflow'}</div>
    </div>
    <div class="card">
      <div class="label">Recommended Session</div>
      <div class="value">${recommendation.plan?.title || '—'}</div>
      <div class="muted">sport: ${recommendation.plan?.sport_type || '—'} • schema: ${recommendation.plan?.schema_version || '—'}</div>
      <ul>${blocks}</ul>
    </div>
    <div class="card">
      <div class="label">7-Day Firm Horizon</div>
      <div class="muted">Phase: ${horizon?.periodization?.phase || '—'} • ${horizon?.periodization?.reason || '—'}</div>
      <div class="muted">Coach Mode: ${horizon?.coach_mode ? 'ON' : 'OFF'}${horizon?.coach_horizon_summary ? ` • TP days: ${horizon.coach_horizon_summary.tp_days_with_plan}/${horizon.coach_horizon_summary.total_days}` : ''}</div>
      <ul>${weekRows}</ul>
    </div>
  `;
}

function attachPlanHandlers() {
  const select = document.getElementById('sportSelect');
  const btn = document.getElementById('applySportBtn');
  const coachToggle = document.getElementById('coachModeToggle');
  const fbEasy = document.getElementById('fbEasyBtn');
  const fbOk = document.getElementById('fbOkBtn');
  const fbHard = document.getElementById('fbHardBtn');
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
}

function routeName() {
  return (location.hash || '#/').replace('#', '');
}

function setAuthStatus(text) {
  const el = document.getElementById('authStatus');
  if (el) el.textContent = text;
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
      const workout = await fetchWorkoutReview();
      app.innerHTML = renderWorkout(workout);
    } else if (r === '/plan') {
      const selected = getSelectedSport();
      const focus = getFocusSport();
      const athleteFeedback = getAthleteFeedback();
      const coachMode = getCoachMode();
      const [modalities, recommendation, horizon] = await Promise.all([
        fetchModalities(),
        fetchPlanRecommendation(selected, focus, athleteFeedback, coachMode),
        fetchPlanHorizon(selected, focus),
      ]);
      app.innerHTML = renderPlan(modalities, recommendation, horizon);
      attachPlanHandlers();
    } else {
      const payload = await fetchPayload();
      if (r === '/recovery') app.innerHTML = renderRecovery(payload);
      else if (r === '/chat') app.innerHTML = renderChat(payload);
      else app.innerHTML = renderMorning(payload);
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

  tokenInput.value = getToken();

  saveBtn.addEventListener('click', async () => {
    setToken(tokenInput.value);
    await render();
  });

  clearBtn.addEventListener('click', async () => {
    setToken('');
    tokenInput.value = '';
    await render();
  });
}

window.addEventListener('hashchange', render);
initAuthUi();
render();
