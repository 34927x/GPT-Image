import { api } from '@/shared/api';
import { storage } from '@/shared/storage';
import { captureCurrentCookies, hasSessionCookie } from '@/shared/cookies';
import type { UIMessage, BackgroundResponse } from '@/shared/messages';
import { startLoop, stopLoop, isRunning } from './loop';
import { refreshState } from './state';

api.runtime.onInstalled.addListener(async () => {
  if (api.sidePanel) {
    api.sidePanel
      .setPanelBehavior({ openPanelOnActionClick: true })
      .catch(() => {});
  }
  await refreshState();

  const settings = await storage.getSettings();
  if (settings.workerEnabled && settings.serverUrl && settings.workerToken) {
    startLoop();
  }
});

api.runtime.onStartup?.addListener?.(async () => {
  const settings = await storage.getSettings();
  if (settings.workerEnabled && settings.serverUrl && settings.workerToken) {
    startLoop();
  }
});

// MV3 service worker keep-alive
api.alarms.create('keepAlive', { periodInMinutes: 0.5 });
api.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'keepAlive') {
    storage.getSettings().then((s) => {
      if (s.workerEnabled && !isRunning()) startLoop();
    });
  }
});

api.runtime.onMessage.addListener((rawMsg, _sender, sendResponse) => {
  const msg = rawMsg as UIMessage;
  (async () => {
    try {
      const reply = await handle(msg);
      sendResponse({ ok: true, data: reply } satisfies BackgroundResponse);
    } catch (e) {
      sendResponse({
        ok: false,
        error: e instanceof Error ? e.message : String(e),
      } satisfies BackgroundResponse);
    }
  })();
  return true;
});

async function handle(msg: UIMessage) {
  switch (msg.type) {
    case 'getState':
      return await refreshState();

    case 'setSettings': {
      const next = await storage.setSettings(msg.patch);
      const wasRunning = isRunning();
      if (wasRunning) await stopLoop();
      if (next.workerEnabled && next.serverUrl && next.workerToken) {
        startLoop();
      }
      return await refreshState();
    }

    case 'setWorkerEnabled': {
      const next = await storage.setSettings({ workerEnabled: msg.enabled });
      if (msg.enabled && next.serverUrl && next.workerToken) startLoop();
      else stopLoop();
      return await refreshState();
    }

    case 'captureCurrentSession': {
      const cookies = await captureCurrentCookies();
      if (!cookies.length) {
        throw new Error('No cookies found. Log into chatgpt.com in this browser first.');
      }
      if (!hasSessionCookie(cookies)) {
        throw new Error('No session cookie detected — are you logged in?');
      }
      const accounts = await storage.getAccounts();
      const id = `acc_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
      accounts.push({
        id,
        label: msg.label?.trim() || `Account ${accounts.length + 1}`,
        cookies,
        capturedAt: Date.now(),
        errorCount: 0,
      });
      await storage.setAccounts(accounts);
      return await refreshState();
    }

    case 'refreshAccountCookies': {
      // User logged into chatgpt.com again and wants to refresh saved cookies
      // for an existing account.
      const cookies = await captureCurrentCookies();
      if (!cookies.length || !hasSessionCookie(cookies)) {
        throw new Error('No fresh session detected. Log in to chatgpt.com first.');
      }
      const accounts = await storage.getAccounts();
      const a = accounts.find((x) => x.id === msg.id);
      if (!a) throw new Error('Account not found');
      a.cookies = cookies;
      a.capturedAt = Date.now();
      a.errorCount = 0;
      a.rateLimitedUntil = undefined;
      await storage.setAccounts(accounts);
      return await refreshState();
    }

    case 'removeAccount': {
      const accounts = await storage.getAccounts();
      const filtered = accounts.filter((a) => a.id !== msg.id);
      await storage.setAccounts(filtered);
      return await refreshState();
    }

    case 'pingServer': {
      const settings = await storage.getSettings();
      if (!settings.serverUrl || !settings.workerToken) {
        throw new Error('Set server URL and worker token first');
      }
      const url = settings.serverUrl.replace(/\/+$/, '') + '/api/worker/heartbeat';
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Worker-Token': settings.workerToken,
          'X-Worker-Id': await storage.getWorkerId(),
        },
        body: JSON.stringify({
          label: settings.workerLabel || 'Test',
          version: '4.0.0',
          accountsTotal: 0,
          accountsActive: 0,
          jobsToday: 0,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Server replied ${res.status}: ${text.slice(0, 100)}`);
      }
      return { ok: true };
    }
  }
}

export {};
