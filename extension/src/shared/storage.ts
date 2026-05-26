import { api } from './api';

/**
 * Persistent storage for the extension. Lives in `chrome.storage.local`.
 */

export interface Settings {
  /** Sub-folder name under Downloads/ for generated images. */
  downloadFolder: string;
  /** Aspect ratio (currently informational; ChatGPT picks via prompt). */
  defaultSize: '1:1' | '16:9' | '9:16' | '4:3';
  /** ms to wait between consecutive prompts (lets the SPA settle). */
  cooldownAfterRunMs: number;
  /** Settings for the optional server worker mode (customer-facing site). */
  serverUrl: string;
  workerToken: string;
  workerEnabled: boolean;
}

const DEFAULTS: Settings = {
  downloadFolder: 'Bulk-GPT',
  defaultSize: '1:1',
  cooldownAfterRunMs: 2500,
  serverUrl: 'https://bulk-gpt-lemon.vercel.app',
  workerToken: '',
  workerEnabled: false,
};

const KEYS = {
  settings: 'bgt_settings',
  accounts: 'bgt_accounts',
  workerId: 'bgt_worker_id',
  stats: 'bgt_stats',
  batch: 'bgt_current_batch',
} as const;

export interface Account {
  id: string;
  label: string;
  cookies: Cookie[];
  capturedAt: number;
  /** Most recent successful generation timestamp. */
  lastUsedAt?: number;
  /** Locked out until this ms timestamp (rate limit). */
  rateLimitedUntil?: number;
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
  jobsTodayDate: string;
  failsToday: number;
}

export type BatchStatus = 'idle' | 'running' | 'paused' | 'done' | 'error';

export interface BatchItem {
  id: string;
  prompt: string;
  status: 'pending' | 'processing' | 'done' | 'failed';
  account?: string;
  error?: string;
  /** Local download path (relative to Downloads/). */
  filename?: string;
  startedAt?: number;
  finishedAt?: number;
}

export interface Batch {
  id: string;
  size: Settings['defaultSize'];
  status: BatchStatus;
  items: BatchItem[];
  createdAt: number;
  /** Last error message if status === 'error'. */
  message?: string;
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
  async getSettings(): Promise<Settings> {
    return { ...DEFAULTS, ...(await get(KEYS.settings, {})) };
  },
  async setSettings(patch: Partial<Settings>): Promise<Settings> {
    const next = { ...(await this.getSettings()), ...patch };
    await set(KEYS.settings, next);
    return next;
  },

  getAccounts: () => get<Account[]>(KEYS.accounts, []),
  setAccounts: (a: Account[]) => set(KEYS.accounts, a),

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

  getBatch: () => get<Batch | null>(KEYS.batch, null),
  setBatch: (b: Batch | null) => set(KEYS.batch, b),
};
