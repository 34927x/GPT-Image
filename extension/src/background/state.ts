import { api } from '@/shared/api';
import { storage } from '@/shared/storage';
import type { State } from '@/shared/messages';

let snapshot: State = {
  settings: {
    downloadFolder: 'Bulk-GPT',
    defaultSize: '1:1',
    cooldownAfterRunMs: 2500,
    serverUrl: '',
    workerToken: '',
    workerEnabled: false,
  },
  accounts: [],
  stats: { jobsToday: 0, jobsTotal: 0, jobsTodayDate: '', failsToday: 0 },
  workerId: '',
  status: 'idle',
  batch: null,
};

export async function refreshState(patch?: Partial<State>): Promise<State> {
  const [settings, accounts, stats, workerId, batch] = await Promise.all([
    storage.getSettings(),
    storage.getAccounts(),
    storage.getStats(),
    storage.getWorkerId(),
    storage.getBatch(),
  ]);
  snapshot = { ...snapshot, settings, accounts, stats, workerId, batch, ...(patch ?? {}) };
  api.runtime.sendMessage({ type: 'stateUpdate', state: snapshot }).catch(() => {});
  return snapshot;
}

export function getSnapshot(): State {
  return snapshot;
}

export function patchStatus(patch: Partial<State>) {
  snapshot = { ...snapshot, ...patch };
  api.runtime.sendMessage({ type: 'stateUpdate', state: snapshot }).catch(() => {});
}
