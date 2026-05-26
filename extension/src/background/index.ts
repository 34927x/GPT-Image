import { api } from '@/shared/api';
import { storage } from '@/shared/storage';
import { captureCurrentCookies, hasSessionCookie } from '@/shared/cookies';
import type { UIMessage, BackgroundResponse } from '@/shared/messages';
import { startLoop, stopLoop, isRunning } from './loop';
import { refreshState, getSnapshot } from './state';
import { switchToAccount } from './account-manager';

api.runtime.onInstalled.addListener(async () => {
  if (api.sidePanel) {
    api.sidePanel
      .setPanelBehavior({ openPanelOnActionClick: true })
      .catch(() => {});
  }
  await refreshState();

  // If worker was previously enabled, resume
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

// Wake-up alarm so the service worker stays alive while polling
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
  return true; // async response
});

async function handle(msg: UIMessage) {
  switch (msg.type) {
    case 'getState':
      return await refreshState();

    case 'setSettings': {
      const next = await storage.setSettings(msg.patch);
      // If serverUrl/workerToken changed, reset loop
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
        throw new Error('No cookies found. Log into chatgpt.com first.');
      }
      if (!hasSessionCookie(cookies)) {
        throw new Error('No session cookie detected. Are you logged in?');
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
      await storage.setActiveIndex(accounts.length - 1);
      return await refreshState();
    }

    case 'removeAccount': {
      const accounts = await storage.getAccounts();
      const filtered = accounts.filter((a) => a.id !== msg.id);
      await storage.setAccounts(filtered);
      const idx = await storage.getActiveIndex();
      if (idx >= filtered.length) {
        await storage.setActiveIndex(Math.max(0, filtered.length - 1));
      }
      return await refreshState();
    }

    case 'switchToAccount': {
      await switchToAccount(msg.id);
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
