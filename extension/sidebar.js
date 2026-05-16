const api = typeof browser !== 'undefined' ? browser : chrome;

const S = {
  accounts: [], activeIdx: 0, theme: 'dark',
  queue: [], running: false, paused: false, aborted: false,
  images: [] // collected for zip
};

const $ = id => document.getElementById(id);
const el = {};

function cache() {
  'statusText,acctCount,accountList,captureBtn,rotateBtn,exportBtn,importBtn,captureForm,labelInput,saveCapture,cancelCapture,importFile,promptsInput,queueStart,queueStop,queueClear,loadTxtBtn,txtFile,statsArea,statDone,statTotal,statFail,statLeft,progressBar,queueLog,downloadZipBtn,themeBtn,themeDark,themeLight,openChatGPT,refreshCookies,serverUrl,apiKey,saveServerUrl,serverStatus'.split(',').forEach(id => el[id] = $(id));
}

document.addEventListener('DOMContentLoaded', () => {
  cache();
  initTabs();
  initCapture();
  initRotate();
  initExportImport();
  initBulk();
  initSettings();
  loadTheme();
  loadAccounts();

  api.runtime.onMessage.addListener(msg => {
    if (msg.action === 'accountsChanged') loadAccounts();
    else if (msg.action === 'accountSwitched') { S.activeIdx = msg.index; loadAccounts(); setSt('Switched ✓'); }
    else if (msg.action === 'rotated') { setSt('Rotated to ' + msg.label); }
    else if (msg.action === 'rateLimitHit') { onRateLimit(); }
  });
});

function initTabs() {
  document.querySelectorAll('.nv-b').forEach(t => {
    t.onclick = () => {
      document.querySelectorAll('.nv-b, .pn').forEach(e => e.classList.remove('active'));
      t.classList.add('active');
      const p = $('pn-' + t.dataset.tab);
      if (p) p.classList.add('active');
      if (t.dataset.tab === 'accounts') loadAccounts();
    };
  });
}

function setSt(msg, type) {
  el.statusText.textContent = msg;
  $('statusBar').className = 'st' + (type ? ' ' + type : '');
}

/* ===== THEME ===== */
function loadTheme() {
  api.storage.local.get('gpt_theme').then(r => { S.theme = r.gpt_theme || 'dark'; applyTheme(); });
}
function applyTheme() {
  document.documentElement.className = S.theme;
  el.themeBtn.textContent = S.theme === 'dark' ? '☀️' : '🌙';
  [el.themeDark, el.themeLight].forEach(b => { if (b) b.className = 'b b-o b-s'; });
  if (S.theme === 'dark') el.themeDark.className = 'b b-p b-s';
  else el.themeLight.className = 'b b-p b-s';
}
function initSettings() {
  el.themeBtn.onclick = () => { S.theme = S.theme === 'dark' ? 'light' : 'dark'; api.storage.local.set({ gpt_theme: S.theme }); applyTheme(); };
  el.themeDark.onclick = () => { S.theme = 'dark'; api.storage.local.set({ gpt_theme: 'dark' }); applyTheme(); };
  el.themeLight.onclick = () => { S.theme = 'light'; api.storage.local.set({ gpt_theme: 'light' }); applyTheme(); };
  el.openChatGPT.onclick = () => api.runtime.sendMessage({ action: 'openChatGPT' });
  el.refreshCookies.onclick = async () => { await api.runtime.sendMessage({ action: 'refreshCookies' }); setSt('Cookies refreshed'); };

  // Server URL + API Key
  api.runtime.sendMessage({ action: 'getServerUrl' }).then(url => { if (url) el.serverUrl.value = url; });
  api.runtime.sendMessage({ action: 'getApiKey' }).then(key => { if (key) el.apiKey.value = key; });
  el.saveServerUrl.onclick = async () => {
    const url = el.serverUrl.value.trim();
    const key = el.apiKey.value.trim();
    await api.runtime.sendMessage({ action: 'setServerUrl', url });
    await api.runtime.sendMessage({ action: 'setApiKey', key });
    el.serverStatus.textContent = '✅ Saved';
    setTimeout(() => el.serverStatus.textContent = '', 2000);
    setSt('Server URL & API key saved');
  };
}

/* ===== ACCOUNTS ===== */
async function loadAccounts() {
  S.accounts = await api.runtime.sendMessage({ action: 'getAccounts' });
  S.activeIdx = await api.runtime.sendMessage({ action: 'getActiveIndex' });
  renderAcc();
}
function renderAcc() {
  const a = S.accounts;
  el.acctCount.textContent = a.length;
  if (!a || !a.length) {
    el.accountList.innerHTML = '<div class="em">No accounts yet.<br>Login to <b>chatgpt.com</b> → Capture</div>';
    setSt('Capture your first account'); return;
  }
  setSt(a[S.activeIdx] ? 'Active: ' + a[S.activeIdx].label : 'None');
  el.accountList.innerHTML = a.map((ac, i) => {
    const act = i === S.activeIdx;
    return `<div class="ai ${act ? 'on' : ''}" data-i="${i}"><div class="rd ${act ? 'on' : ''}"></div><div class="aii"><div class="ain">${esc(ac.label)}</div><div class="aim">${ac.cookies?.length || 0} cookies</div></div><div class="aia">${act ? '<span class="aib">ACTIVE</span>' : '<button class="b b-p b-s ac-sw">Switch</button>'}<button class="b b-d b-s ac-rm">✕</button></div></div>`;
  }).join('');

  el.accountList.querySelectorAll('.ai').forEach(d => {
    const i = parseInt(d.dataset.i);
    d.querySelector('.ac-sw')?.addEventListener('click', async e => {
      e.stopPropagation();
      const r = await api.runtime.sendMessage({ action: 'switchToAccount', index: i });
      if (r.success) { S.activeIdx = i; loadAccounts(); setSt('Switched to ' + r.label); }
      else setSt(r.error || 'Failed', 'er');
    });
    d.querySelector('.ac-rm').addEventListener('click', async e => {
      e.stopPropagation();
      await api.runtime.sendMessage({ action: 'removeAccount', index: i });
      loadAccounts();
    });
    d.onclick = async () => {
      if (i === S.activeIdx) return;
      const r = await api.runtime.sendMessage({ action: 'switchToAccount', index: i });
      if (r.success) loadAccounts();
    };
  });
}

/* ===== CAPTURE ===== */
function initCapture() {
  el.captureBtn.onclick = () => { el.captureForm.classList.toggle('sh'); if (el.captureForm.classList.contains('sh')) el.labelInput.focus(); };
  el.cancelCapture.onclick = () => el.captureForm.classList.remove('sh');
  el.saveCapture.onclick = async () => {
    const label = el.labelInput.value.trim() || ('Acct-' + Date.now());
    el.saveCapture.disabled = true; el.saveCapture.textContent = '...';
    const r = await api.runtime.sendMessage({ action: 'captureSession', label });
    el.saveCapture.disabled = false; el.saveCapture.textContent = 'Save';
    if (r.success) { el.captureForm.classList.remove('sh'); el.labelInput.value = ''; setSt('Captured: ' + label); loadAccounts(); }
    else setSt(r.error || 'Failed', 'er');
  };
}

/* ===== ROTATE ===== */
function initRotate() {
  el.rotateBtn.onclick = async () => {
    const r = await api.runtime.sendMessage({ action: 'rotateNext' });
    if (r.success) { setSt('Rotated to ' + r.label); loadAccounts(); }
    else setSt(r.error || 'Failed', 'wa');
  };
}

/* ===== EXPORT/IMPORT ===== */
function initExportImport() {
  el.exportBtn.onclick = async () => {
    const r = await api.runtime.sendMessage({ action: 'exportAccounts' });
    if (!r.data || !r.data.length) { setSt('Nothing to export', 'wa'); return; }
    const blob = new Blob([JSON.stringify(r.data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'gpt-accounts-' + Date.now() + '.json';
    a.click(); URL.revokeObjectURL(url);
    setSt('Exported ' + r.data.length + ' accounts');
  };
  el.importBtn.onclick = () => el.importFile.click();
  el.importFile.onchange = async e => {
    const f = e.target.files[0]; if (!f) return;
    try {
      const txt = await f.text();
      const data = JSON.parse(txt);
      if (!Array.isArray(data)) throw Error('Invalid');
      const res = await api.runtime.sendMessage({ action: 'importAccounts', data });
      if (res.success) { setSt('Imported ' + res.count + ' accounts'); loadAccounts(); }
      else setSt(res.error || 'Failed', 'er');
    } catch (err) { setSt('File: ' + err.message, 'er'); }
    el.importFile.value = '';
  };
}

/* ===== BULK ===== */
function initBulk() {
  el.queueStart.onclick = () => {
    if (S.running && !S.paused) return;
    if (!S.running) {
      const raw = el.promptsInput.value.trim();
      if (!raw) { setSt('Enter prompts first', 'wa'); return; }
      S.queue = parsePrompts(raw);
      if (!S.queue.length) { setSt('No valid prompts', 'wa'); return; }
      S.running = true; S.paused = false; S.aborted = false;
      S.images = [];
      el.downloadZipBtn.disabled = true;
      renderQueue();
      el.statsArea.classList.add('sh');
      el.queueStart.textContent = '⏳ Running...';
      processQueue();
    } else if (S.paused) {
      S.paused = false; S.aborted = false;
      el.queueStart.textContent = '⏳ Running...';
      setSt('Resumed'); processQueue();
    }
  };

  el.queueStop.onclick = () => {
    if (!S.running) return;
    S.paused = true; el.queueStart.textContent = '▶ Resume'; setSt('Paused', 'wa');
  };

  el.queueClear.onclick = () => {
    S.queue = []; S.running = false; S.paused = false; S.aborted = true; S.images = [];
    el.promptsInput.value = ''; el.queueLog.innerHTML = ''; el.statsArea.classList.remove('sh');
    el.progressBar.style.width = '0'; el.queueStart.textContent = '▶ Start';
    el.downloadZipBtn.disabled = false; setSt('Cleared');
  };

  el.loadTxtBtn.onclick = () => el.txtFile.click();
  el.txtFile.onchange = async e => {
    const f = e.target.files[0]; if (!f) return;
    el.promptsInput.value = await f.text(); el.txtFile.value = ''; setSt('Loaded ' + f.name);
  };

  el.downloadZipBtn.onclick = downloadZip;
}

function parsePrompts(raw) {
  const blocks = raw.split(/\n\s*\n/).map(s => s.trim()).filter(s => s.length > 0);
  if (blocks.length < 2) return raw.split('\n').map(s => s.trim()).filter(s => s.length > 0).map((s, i) => ({ id: i + 1, prompt: s, status: 'pending' }));
  return blocks.map((s, i) => ({ id: i + 1, prompt: s, status: 'pending' }));
}

function renderQueue() {
  el.queueLog.innerHTML = '';
  S.queue.forEach(q => {
    const d = document.createElement('div');
    d.id = 'ql-' + q.id;
    d.innerHTML = '<span class="qlp">#' + q.id + ': ' + esc(q.prompt.substring(0, 55)) + '</span><span class="qls">⏳</span>';
    el.queueLog.appendChild(d);
  });
  updateStats();
}

function updateStats() {
  const total = S.queue.length, done = S.queue.filter(q => q.status === 'done').length, fail = S.queue.filter(q => q.status === 'fail').length;
  el.statDone.textContent = done; el.statTotal.textContent = total; el.statFail.textContent = fail;
  el.statLeft.textContent = total - done - fail;
  el.progressBar.style.width = total ? ((done + fail) / total * 100) + '%' : '0';
  S.queue.forEach(q => {
    const el2 = $('ql-' + q.id); if (!el2) return;
    const sp = el2.querySelector('.qls'); if (!sp) return;
    if (q.status === 'processing') { sp.textContent = '⏳'; el2.className = ''; }
    else if (q.status === 'done') { sp.textContent = '✅'; el2.className = 'do'; }
    else if (q.status === 'fail') { sp.textContent = '❌'; el2.className = 'fa'; }
  });
}

/* ===== QUEUE ENGINE ===== */
async function processQueue() {
  while (S.running && !S.paused && !S.aborted) {
    const next = S.queue.find(q => q.status === 'pending');
    if (!next) {
      const d = S.queue.filter(q => q.status === 'done').length;
      setSt('✅ Complete! ' + d + '/' + S.queue.length);
      S.running = false; el.queueStart.textContent = '▶ Start';
      el.downloadZipBtn.disabled = false;
      if (S.images.length) setSt('📦 ' + S.images.length + ' images ready for ZIP', '');
      return;
    }

    next.status = 'processing'; updateStats(); updateQl(next.id, 'sending...');
    setSt('#' + next.id + ': ' + next.prompt.substring(0, 40));

    const result = await sendToChatGPT(next.prompt);
    const ok = result && result.success;

    // If image was generated, store for zip
    if (ok && result.imageUrl) {
      S.images.push({ url: result.imageUrl, prompt: next.prompt, index: next.id });
    }

    next.status = ok ? 'done' : 'fail'; updateStats(); updateQl(next.id, ok ? '✅' : '❌');

    if (S.aborted) break;
    // 3s delay AFTER the prompt is done (image generated or failed)
    if (!S.aborted) await sleep(3000);
  }
  if (S.paused && !S.aborted) setSt('Paused', 'wa');
}

async function sendToChatGPT(prompt) {
  const r = await api.runtime.sendMessage({
    action: 'relayToContent',
    msg: { action: 'submitPrompt', prompt }
  });
  if (r.error) { setSt('Error: ' + r.error, 'er'); return null; }
  if (r.aborted) { setSt('Aborted', 'wa'); return null; }
  // Return the result from content.js which includes { success, image, imageUrl }
  return r;
}

/* ===== ZIP DOWNLOAD ===== */
async function downloadZip() {
  const imgs = S.images.length ? S.images :
    S.queue.filter(q => q.status === 'done').map(q => ({ prompt: q.prompt, index: q.id }));

  if (!imgs.length) { setSt('No images to download', 'wa'); return; }

  setSt('Creating ZIP with ' + imgs.length + ' images...');
  el.downloadZipBtn.disabled = true;

  const files = [];
  for (const img of imgs) {
    let url = img.url;
    // If no stored URL, try to fetch from queue (for completed queue without stored URLs)
    if (!url) continue;

    try {
      // Generate filename: 001-prompt-words-By @TurabCoder.png
      const fname = makeFilename(img.index, img.prompt);
      const resp = await fetch(url);
      const blob = await resp.blob();
      files.push({ name: fname, data: blob });
    } catch (e) {
      console.warn('Failed to fetch image', img.index, e.message);
    }
  }

  if (!files.length) { setSt('No images could be downloaded', 'er'); el.downloadZipBtn.disabled = false; return; }

  try {
    const zipBlob = await self.GPTZip.create(files);
    const zipUrl = URL.createObjectURL(zipBlob);
    const a = document.createElement('a');
    a.href = zipUrl; a.download = 'GPT-Images-' + Date.now() + '.zip';
    a.click();
    setTimeout(() => URL.revokeObjectURL(zipUrl), 5000);
    setSt('📦 Downloaded: ' + files.length + ' images');
  } catch (e) {
    setSt('ZIP failed: ' + e.message, 'er');
  }
  el.downloadZipBtn.disabled = false;
}

function makeFilename(index, prompt) {
  // Format: 001-first-3-4-words-By @TurabCoder.png
  const num = String(index).padStart(3, '0');
  const words = prompt.trim()
    .replace(/[^a-zA-Z0-9\s]/g, '')
    .split(/\s+/)
    .filter(w => w.length > 0)
    .slice(0, 4)
    .join('-')
    .toLowerCase();
  return num + '-' + words + '-By @TurabCoder.png';
}

function updateQl(id, text) {
  const e = $('ql-' + id);
  if (e) { const sp = e.querySelector('.qls'); if (sp) sp.textContent = text; }
}

/* ===== RATE LIMIT ===== */
function onRateLimit() {
  setSt('⚠️ Rate limit! Rotating...', 'wa');
  S.running = false; S.paused = true;
  el.queueStart.textContent = '▶ Resume';
  if (S.queue.some(q => q.status === 'pending')) {
    setTimeout(async () => {
      await api.runtime.sendMessage({ action: 'rotateNext' });
      setSt('Rotated. Reload chatgpt tab and Resume.', 'wa');
    }, 1000);
  }
}

/* ===== UTILS ===== */
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function esc(s) { if (!s) return ''; const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
