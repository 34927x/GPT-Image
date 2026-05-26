import type { Account } from './storage';

// ============ UI ↔ Background ============
export type UIMessage =
  | { type: 'getState' }
  | { type: 'setSettings'; patch: Partial<import('./storage').WorkerSettings> }
  | { type: 'setWorkerEnabled'; enabled: boolean }
  | { type: 'captureCurrentSession'; label?: string }
  | { type: 'refreshAccountCookies'; id: string }
  | { type: 'removeAccount'; id: string }
  | { type: 'pingServer' };

export type BackgroundResponse =
  | { ok: true; data?: unknown }
  | { ok: false; error: string };

// ============ Background ↔ Content ============
export type ContentMessage =
  | { type: 'runPrompt'; prompt: string; jobId: string; imageSize: string }
  | { type: 'abort' };

export type ContentResponse =
  | { type: 'success'; imageDataUrl: string }
  | { type: 'rateLimited'; resetAt?: number }
  | { type: 'failure'; error: string };

// ============ Server ============
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
export interface WorkerState {
  settings: import('./storage').WorkerSettings;
  accounts: Account[];
  stats: import('./storage').Stats;
  workerId: string;
  status: 'idle' | 'polling' | 'processing' | 'paused' | 'error';
  currentJob?: { id: string; prompt: string };
  lastError?: string;
}
