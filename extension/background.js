const STORAGE_KEY = 'gpt_accounts_v2';
const ACTIVE_KEY = 'gpt_active_account_v2';
const CAPTURE_DOMAINS = ['chatgpt.com', '.openai.com'];
const RATE_LIMIT_THRESHOLD = 2;

let rateHitCount = 0;
let isRotating = false;

const api = typeof browser !== 'undefined' ? browser : chrome;

api.runtime.onInstalled.addListener(() => {
  api.alarms.create('healthCheck', { periodInMinutes: 15 });
  if (api.sidePanel) {
    api.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
  }
});

api.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === 'healthCheck') refreshCurrentCookies();
});

async function sGet(key, def) {
  const r = await api.storage.local.get(key);
  return r[key] ?? def;
}
function sSet(key, val) {
  return api.storage.local.set({ [key]: val });
}

api.runtime.onMessage.addListener((req, sender, sendResponse) => {
  const h = async () => {
    try {
      switch (req.action) {
        case 'getAccounts': return await sGet(STORAGE_KEY, []);
        case 'getActiveIndex': return await sGet(ACTIVE_KEY, 0);
        case 'captureSession': return await captureSession(req.label);
        case 'removeAccount': return await removeAccount(req.index);
        case 'switchToAccount': return await switchToAccount(req.index);
        case 'rotateNext': return await rotateNext();
        case 'exportAccounts': return await exportAccounts();
        case 'importAccounts': return await importAccounts(req.data);
        case 'downloadImage': return await downloadImage(req.url, req.filename);
        case 'rateLimitDetected': return await handleRateLimit();
        case 'refreshCookies': return await refreshCurrentCookies();
        case 'relayToContent': return await relayToChatGPT(req.msg);
        case 'openChatGPT': await api.tabs.create({ url: 'https://chatgpt.com' }); return { ok: 1 };
        case 'getServerUrl': return await sGet(SERVER_URL_KEY, '');
        case 'setServerUrl': await sSet(SERVER_URL_KEY, req.url); return { ok: 1 };
        case 'pushCookies': return await pushCookiesToServer(req.label, req.cookies);
      }
    } catch (e) { return { error: e.message }; }
  };
  h().then(sendResponse);
  return true;
});

async function captureSession(label) {
  const cookies = [];
  for (const domain of CAPTURE_DOMAINS) {
    try {
      for (const c of await api.cookies.getAll({ domain }))
        cookies.push({ name: c.name, value: c.value, domain: c.domain, path: c.path, secure: c.secure, httpOnly: c.httpOnly, sameSite: c.sameSite });
    } catch (e) {}
  }
  if (!cookies.length) return { success: false, error: 'No cookies. Login on chatgpt.com first.' };
  if (!cookies.some(c => /session|token|auth/i.test(c.name)))
    return { success: false, error: 'No session found.' };

  const accounts = await sGet(STORAGE_KEY, []);
  accounts.push({ id: crypto.randomUUID(), label: label || 'Account ' + (accounts.length + 1), cookies, capturedAt: Date.now() });
  await sSet(STORAGE_KEY, accounts);
  await sSet(ACTIVE_KEY, accounts.length - 1);
  notify({ action: 'accountsChanged' });

  // Auto-push to server if configured
  pushCookiesToServer(label, cookies).then(r => {
    if (r.pushed) console.log('Cookies pushed to server:', r.result);
  });

  return { success: true, accounts, activeIndex: accounts.length - 1 };
}

async function removeAccount(index) {
  let a = await sGet(STORAGE_KEY, []);
  if (index < 0 || index >= a.length) return { ok: 0 };
  a.splice(index, 1); await sSet(STORAGE_KEY, a);
  let act = await sGet(ACTIVE_KEY, 0);
  if (act >= a.length) await sSet(ACTIVE_KEY, Math.max(0, a.length - 1));
  notify({ action: 'accountsChanged' });
  return { ok: 1 };
}

async function switchToAccount(index) {
  if (isRotating) return { success: false, error: 'Busy' };
  isRotating = true;
  try {
    const a = await sGet(STORAGE_KEY, []);
    if (index < 0 || index >= a.length) return { success: false, error: 'Invalid' };
    await clearAllCookies();
    await restoreCookies(a[index].cookies);
    await sSet(ACTIVE_KEY, index);
    rateHitCount = 0;
    notify({ action: 'accountSwitched', index, label: a[index].label });
    return { success: true, activeIndex: index, label: a[index].label };
  } finally { isRotating = false; }
}

async function rotateNext() {
  const a = await sGet(STORAGE_KEY, []);
  if (!a.length) return { success: false, error: 'No accounts' };
  return await switchToAccount((await sGet(ACTIVE_KEY, 0) + 1) % a.length);
}

async function handleRateLimit() {
  rateHitCount++;
  if (rateHitCount >= RATE_LIMIT_THRESHOLD && !isRotating) {
    rateHitCount = 0; notify({ action: 'rateLimitHit' });
    const r = await rotateNext();
    if (r.success) notify({ action: 'rotated', label: r.label });
    return r;
  }
  return { success: false };
}

async function exportAccounts() {
  const a = await sGet(STORAGE_KEY, []);
  return { data: a.map(x => ({ id: x.id, label: x.label, capturedAt: x.capturedAt, cookies: x.cookies })) };
}

async function importAccounts(raw) {
  if (!Array.isArray(raw)) return { error: 'Invalid format' };
  const v = raw.filter(x => x.cookies && Array.isArray(x.cookies) && x.cookies.length);
  if (!v.length) return { error: 'No valid accounts' };
  const existing = await sGet(STORAGE_KEY, []);
  for (const x of v) existing.push({ id: crypto.randomUUID(), label: x.label || 'Imported', cookies: x.cookies, capturedAt: x.capturedAt || Date.now() });
  await sSet(STORAGE_KEY, existing);
  notify({ action: 'accountsChanged' });
  return { success: true, count: v.length };
}

async function clearAllCookies() {
  for (const domain of CAPTURE_DOMAINS) {
    for (const c of await api.cookies.getAll({ domain })) {
      const d = c.domain.startsWith('.') ? c.domain.slice(1) : c.domain;
      try { await api.cookies.remove({ url: `https://${d}${c.path}`, name: c.name }); } catch {}
    }
  }
}

async function restoreCookies(cookies) {
  for (const c of cookies) {
    const d = c.domain.startsWith('.') ? c.domain.slice(1) : c.domain;
    try { await api.cookies.set({ url: `https://${d}${c.path}`, name: c.name, value: c.value, domain: c.domain, path: c.path, secure: c.secure, httpOnly: c.httpOnly, sameSite: c.sameSite }); }
    catch (e) { console.warn('cookie:', c.name, e.message); }
  }
}

// ── Push cookies to server (auto-sync to MongoDB) ──
const SERVER_URL_KEY = 'gpt_server_url';

async function pushCookiesToServer(label, cookies) {
  const serverUrl = await sGet(SERVER_URL_KEY, '');
  if (!serverUrl) return { pushed: false, reason: 'No server URL set' };
  try {
    const resp = await fetch(serverUrl.replace(/\/+$/, '') + '/api/cookies', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label, cookies })
    });
    const result = await resp.json();
    return { pushed: true, result };
  } catch (e) {
    console.warn('pushCookiesToServer failed:', e.message);
    return { pushed: false, reason: e.message };
  }
}

async function refreshCurrentCookies() {
  const a = await sGet(STORAGE_KEY, []), act = await sGet(ACTIVE_KEY, 0);
  if (!a[act]) return;
  const cks = [];
  for (const domain of CAPTURE_DOMAINS)
    for (const c of await api.cookies.getAll({ domain }))
      cks.push({ name: c.name, value: c.value, domain: c.domain, path: c.path, secure: c.secure, httpOnly: c.httpOnly, sameSite: c.sameSite });
  if (cks.length) { a[act].cookies = cks; a[act].capturedAt = Date.now(); await sSet(STORAGE_KEY, a); }
}

async function downloadImage(url, filename) {
  try { return { ok: 1, id: await api.downloads.download({ url, filename: filename || 'image.png', saveAs: false }) }; }
  catch (e) { return { error: e.message }; }
}

async function relayToChatGPT(msg) {
  const tabs = await api.tabs.query({ url: 'https://chatgpt.com/*' });
  for (const t of tabs)
    try { const r = await api.tabs.sendMessage(t.id, msg); return r || { ok: 1 }; } catch (e) {}
  return { error: 'No chatgpt.com tab' };
}

function notify(msg) { api.runtime.sendMessage(msg).catch(() => {}); }

api.webRequest.onHeadersReceived.addListener(
  d => { if (d.statusCode === 429) handleRateLimit(); },
  { urls: ['https://chatgpt.com/*', 'https://*.openai.com/*'] },
  ['responseHeaders']
);
