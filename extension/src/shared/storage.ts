import { api } from './api';

/**
 * Persistent storage for the worker. Keys live in `chrome.storage.local`.
 */

export interface WorkerSettings {
  serverUrl: string;
  workerToken: string;
  workerLabel: string;
  workerEnabled: boolean;
  pollIntervalMs: number;
  cooldownAfterRunMs: number;
  rateLimitThreshold: number; // consecutive 429s before rotation
}

const DEFAULTS: WorkerSettings = {
  serverUrl: '',
  workerToken: '',
  workerLabel: '',
  workerEnabled: false,
  pollIntervalMs: 5000,
  cooldownAfterRunMs: 3000,
  rateLimitThreshold: 2,
};

const KEYS = {
  settings: 'bgt_worker_settings',
  accounts: 'bgt_accounts',
  activeIdx: 'bgt_active_idx',
  workerId: 'bgt_worker_id',
  stats: 'bgt_stats',
} as const;

export interface Account {
  id: string;
  label: string;
  cookies: Cookie[];
  capturedAt: number;
  rateLimitedUntil?: number;
  lastUsedAt?: number;
  errorCount: number;
}

export interface Cookie {
  name: string;
  value: string;
  domain: string;
  path: string;
  secure?: boolean;
  httpOnly?: boolean;
  sameSite?: 'no_restriction' | 'lax' | 'strict' | 'unspecified';
  expirationDate?: number;
}

export interface Stats {
  jobsToday: number;
  jobsTotal: number;
  jobsTodayDate: string; // YYYY-MM-DD
  failsToday: number;
}

const todayKey = () => new Date().toISOString().slice(0, 10);

async function get<T>(key: string, fallback: T): Promise<T> {
  const r = await api.storage.local.get(key);
  return (r[key] as T) ?? fallback;
}

function set<T>(key: string, value: T): Promise<void> {
  return api.storage.local.set({ [key]: value });
}

export const storage = {
  async getSettings(): Promise<WorkerSettings> {
    return { ...DEFAULTS, ...(await get(KEYS.settings, {})) };
  },
  async setSettings(patch: Partial<WorkerSettings>): Promise<WorkerSettings> {
    const next = { ...(await this.getSettings()), ...patch };
    await set(KEYS.settings, next);
    return next;
  },

  getAccounts: () => get<Account[]>(KEYS.accounts, []),
  setAccounts: (a: Account[]) => set(KEYS.accounts, a),

  getActiveIndex: () => get<number>(KEYS.activeIdx, 0),
  setActiveIndex: (i: number) => set(KEYS.activeIdx, i),

  async getWorkerId(): Promise<string> {
    const existing = await get<string>(KEYS.workerId, '');
    if (existing) return existing;
    const fresh =
      'w-' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
    await set(KEYS.workerId, fresh);
    return fresh;
  },

  async getStats(): Promise<Stats> {
    const s = await get<Stats>(KEYS.stats, {
      jobsToday: 0,
      jobsTotal: 0,
      jobsTodayDate: todayKey(),
      failsToday: 0,
    });
    if (s.jobsTodayDate !== todayKey()) {
      const reset = { ...s, jobsToday: 0, failsToday: 0, jobsTodayDate: todayKey() };
      await set(KEYS.stats, reset);
      return reset;
    }
    return s;
  },
  async incStats(patch: { ok?: boolean }): Promise<Stats> {
    const s = await this.getStats();
    const next: Stats = {
      ...s,
      jobsTotal: s.jobsTotal + 1,
      jobsToday: s.jobsToday + 1,
      failsToday: patch.ok ? s.failsToday : s.failsToday + 1,
    };
    await set(KEYS.stats, next);
    return next;
  },
};
