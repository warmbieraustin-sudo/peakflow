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
