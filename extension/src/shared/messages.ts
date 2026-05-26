import type { Account, Batch, Settings, Stats } from './storage';

// ============ UI ↔ Background ============
export type UIMessage =
  | { type: 'getState' }
  | { type: 'setSettings'; patch: Partial<Settings> }
  | { type: 'captureCurrentSession'; label?: string }
  | { type: 'refreshAccountCookies'; id: string }
  | { type: 'removeAccount'; id: string }
  | { type: 'startBatch'; prompts: string[]; size: Settings['defaultSize'] }
  | { type: 'pauseBatch' }
  | { type: 'resumeBatch' }
  | { type: 'stopBatch' }
  | { type: 'clearBatch' }
  | { type: 'pingServer' }
  | { type: 'setWorkerEnabled'; enabled: boolean };

export type BackgroundResponse =
  | { ok: true; data?: unknown }
  | { ok: false; error: string };

// ============ Background ↔ Content (chatgpt.com tab) ============
export type ContentMessage =
  | { type: 'runPrompt'; prompt: string; jobId: string; imageSize: string }
  | { type: 'abort' };

export type ContentResponse =
  | { type: 'success'; imageDataUrl: string }
  | { type: 'rateLimited'; resetAt?: number }
  | { type: 'failure'; error: string };

// ============ Server (worker mode, optional) ============
export interface ServerJob {
  id: string;
  prompt: string;
  imageSize: '1:1' | '16:9' | '9:16' | '4:3';
  attempts: number;
}

export interface CompleteSuccess {
  outcome: 'success';
  jobId: string;
  imageDataUrl: string;
  account?: string;
}

export interface CompleteFailure {
  outcome: 'failure';
  jobId: string;
  error: string;
}

// ============ Live state pushed to UI ============
export interface State {
  settings: Settings;
  accounts: Account[];
  stats: Stats;
  workerId: string;
  status: 'idle' | 'running' | 'paused' | 'error';
  currentItem?: { id: string; prompt: string; account?: string };
  lastError?: string;
  batch: Batch | null;
}
