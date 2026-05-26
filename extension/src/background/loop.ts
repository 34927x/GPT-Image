import { storage } from '@/shared/storage';
import { server } from '@/shared/server';
import {
  pickNextAccount,
  markAccountRateLimited,
  markAccountError,
  markAccountSuccess,
  updateAccountCookies,
} from './account-manager';
import { executeIncognito } from './runner';
import { buildHeartbeatSnapshot, patchStatus, refreshState } from './state';

let running = false;
let stopRequested = false;
let pollTimer: ReturnType<typeof setTimeout> | null = null;
let heartbeatTimer: ReturnType<typeof setInterval> | null = null;

export function isRunning() {
  return running;
}

export async function startLoop(): Promise<void> {
  if (running) return;
  running = true;
  stopRequested = false;
  patchStatus({ status: 'polling', lastError: undefined });

  await safeHeartbeat();
  heartbeatTimer = setInterval(safeHeartbeat, 15_000);

  loop();
}

export async function stopLoop(): Promise<void> {
  stopRequested = true;
  running = false;
  if (pollTimer) clearTimeout(pollTimer);
  if (heartbeatTimer) clearInterval(heartbeatTimer);
  pollTimer = null;
  heartbeatTimer = null;
  patchStatus({ status: 'idle', currentJob: undefined });
}

async function loop(): Promise<void> {
  while (!stopRequested) {
    const settings = await storage.getSettings();
    if (!settings.workerEnabled) break;

    try {
      patchStatus({ status: 'polling' });
      const job = await server.claim();

      if (!job) {
        await sleep(settings.pollIntervalMs);
        continue;
      }

      // Pick an account
      const account = await pickNextAccount();
      if (!account) {
        await server.complete({
          outcome: 'failure',
          jobId: job.id,
          error: 'No active accounts available (all rate-limited or none added)',
        });
        patchStatus({
          status: 'paused',
          lastError: 'All accounts rate-limited or none added.',
        });
        // Long backoff so we don't keep hammering the queue
        await sleep(60_000);
        continue;
      }

      patchStatus({
        status: 'processing',
        currentJob: { id: job.id, prompt: job.prompt },
      });

      const { result, refreshedCookies } = await executeIncognito({
        jobId: job.id,
        prompt: job.prompt,
        imageSize: job.imageSize,
        account,
      });

      if (result.type === 'success') {
        await server.complete({
          outcome: 'success',
          jobId: job.id,
          imageDataUrl: result.imageDataUrl,
          account: account.label,
        });
        await markAccountSuccess(account.id);
        if (refreshedCookies && refreshedCookies.length) {
          await updateAccountCookies(account.id, refreshedCookies);
        }
        await storage.incStats({ ok: true });
      } else if (result.type === 'rateLimited') {
        await markAccountRateLimited(account.id, result.resetAt);
        await server.complete({
          outcome: 'failure',
          jobId: job.id,
          error: 'Rate limited — rotated account, please retry',
        });
        await storage.incStats({ ok: false });
      } else {
        await markAccountError(account.id);
        await server.complete({
          outcome: 'failure',
          jobId: job.id,
          error: result.error.slice(0, 480),
        });
        await storage.incStats({ ok: false });
      }

      patchStatus({ status: 'polling', currentJob: undefined });
      await refreshState();
      await sleep(settings.cooldownAfterRunMs);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      patchStatus({ status: 'error', lastError: msg });
      console.error('[bgt] loop error', msg);
      await sleep(8_000);
    }
  }

  running = false;
  patchStatus({ status: 'idle', currentJob: undefined });
}

async function safeHeartbeat(): Promise<void> {
  try {
    const snap = await buildHeartbeatSnapshot();
    await server.heartbeat(snap);
  } catch {
    /* heartbeat failures are non-fatal */
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    pollTimer = setTimeout(resolve, ms);
  });
}
