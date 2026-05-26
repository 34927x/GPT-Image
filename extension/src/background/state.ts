import { api } from '@/shared/api';
import { storage } from '@/shared/storage';
import { activeAccountsCount } from './account-manager';
import type { WorkerState } from '@/shared/messages';

let snapshot: WorkerState = {
  settings: {
    serverUrl: '',
    workerToken: '',
    workerLabel: '',
    workerEnabled: false,
    pollIntervalMs: 5000,
    cooldownAfterRunMs: 3000,
    rateLimitThreshold: 2,
  },
  accounts: [],
  activeIdx: 0,
  stats: { jobsToday: 0, jobsTotal: 0, jobsTodayDate: '', failsToday: 0 },
  workerId: '',
  status: 'idle',
};

export async function refreshState(patch?: Partial<WorkerState>): Promise<WorkerState> {
  const [settings, accounts, activeIdx, stats, workerId] = await Promise.all([
    storage.getSettings(),
    storage.getAccounts(),
    storage.getActiveIndex(),
    storage.getStats(),
    storage.getWorkerId(),
  ]);
  snapshot = { ...snapshot, settings, accounts, activeIdx, stats, workerId, ...(patch ?? {}) };
  // Push to any open UI
  api.runtime.sendMessage({ type: 'stateUpdate', state: snapshot }).catch(() => {});
  return snapshot;
}

export function getSnapshot(): WorkerState {
  return snapshot;
}

export function patchStatus(patch: Partial<WorkerState>) {
  snapshot = { ...snapshot, ...patch };
  api.runtime.sendMessage({ type: 'stateUpdate', state: snapshot }).catch(() => {});
}

export async function buildHeartbeatSnapshot() {
  const settings = await storage.getSettings();
  const accounts = await storage.getAccounts();
  const stats = await storage.getStats();
  return {
    label: settings.workerLabel || 'Unnamed worker',
    version: '4.0.0',
    accountsTotal: accounts.length,
    accountsActive: await activeAccountsCount(),
    jobsToday: stats.jobsToday,
  };
}
