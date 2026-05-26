import type { ServerJob, CompleteSuccess, CompleteFailure } from './messages';
import { storage } from './storage';

class ServerError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function authedFetch(path: string, init?: RequestInit): Promise<Response> {
  const settings = await storage.getSettings();
  if (!settings.serverUrl || !settings.workerToken) {
    throw new ServerError(0, 'Worker not configured. Set server URL & token in Settings.');
  }
  const workerId = await storage.getWorkerId();
  const url = settings.serverUrl.replace(/\/+$/, '') + path;
  const res = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-Worker-Token': settings.workerToken,
      'X-Worker-Id': workerId,
      ...(init?.headers ?? {}),
    },
  });
  return res;
}

export const server = {
  async heartbeat(snapshot: {
    label: string;
    version: string;
    accountsTotal: number;
    accountsActive: number;
    jobsToday: number;
  }): Promise<void> {
    const res = await authedFetch('/api/worker/heartbeat', {
      method: 'POST',
      body: JSON.stringify(snapshot),
    });
    if (!res.ok) throw new ServerError(res.status, await res.text());
  },

  async claim(): Promise<ServerJob | null> {
    const res = await authedFetch('/api/worker/claim', { method: 'POST' });
    if (!res.ok) throw new ServerError(res.status, await res.text());
    const data = (await res.json()) as { job: ServerJob | null };
    return data.job;
  },

  async complete(payload: CompleteSuccess | CompleteFailure): Promise<void> {
    const res = await authedFetch('/api/worker/complete', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new ServerError(res.status, await res.text());
  },
};

export { ServerError };
