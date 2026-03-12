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
  return `<div class="card"><pre>${JSON.stringify(w, null, 2)}</pre></div>`;
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
