async function fetchPayload() {
  const res = await fetch('/api/alpha/shell/today');
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || 'fetch failed');
  return data.payload;
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
  return `
    <div class="card"><pre>${JSON.stringify(r, null, 2)}</pre></div>
  `;
}

function renderChat(p) {
  const c = p.screens.chat_context;
  return `<div class="card"><pre>${JSON.stringify(c, null, 2)}</pre></div>`;
}

function routeName() {
  return (location.hash || '#/').replace('#', '');
}

async function render() {
  const app = document.getElementById('app');
  try {
    const payload = await fetchPayload();
    const r = routeName();
    if (r === '/recovery') app.innerHTML = renderRecovery(payload);
    else if (r === '/chat') app.innerHTML = renderChat(payload);
    else app.innerHTML = renderMorning(payload);
  } catch (e) {
    app.innerHTML = `<div class='card'>Error: ${e.message}</div>`;
  }
}

window.addEventListener('hashchange', render);
render();
