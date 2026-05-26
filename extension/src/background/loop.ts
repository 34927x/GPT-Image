import { storage } from '@/shared/storage';
import { server } from '@/shared/server';
import {
  pickNextAccount,
  switchToAccount,
  markAccountRateLimited,
  markAccountError,
  markAccountSuccess,
  getActiveAccount,
} from './account-manager';
import { executePrompt } from './runner';
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

  // Heartbeat every 15s
  await safeHeartbeat();
  heartbeatTimer = setInterval(safeHeartbeat, 15_000);

  await loop();
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

      patchStatus({ status: 'processing', currentJob: { id: job.id, prompt: job.prompt } });

      // Pick & switch account
      const next = await pickNextAccount();
      if (!next) {
        await server.complete({
          outcome: 'failure',
          jobId: job.id,
          error: 'No active accounts available (all rate-limited)',
        });
        patchStatus({ status: 'paused', lastError: 'All accounts rate-limited.' });
        await sleep(60_000); // backoff
        continue;
      }

      const active = await getActiveAccount();
      const needsReload = !active || active.id !== next.id;
      if (needsReload) {
        const ok = await switchToAccount(next.id);
        if (!ok) {
          await server.complete({
            outcome: 'failure',
            jobId: job.id,
            error: 'Failed to switch account cookies',
          });
          await sleep(settings.cooldownAfterRunMs);
          continue;
        }
      }

      const result = await executePrompt({
        jobId: job.id,
        prompt: job.prompt,
        imageSize: job.imageSize,
        needsReload,
      });

      if (result.type === 'success') {
        await server.complete({
          outcome: 'success',
          jobId: job.id,
          imageDataUrl: result.imageDataUrl,
          account: next.label,
        });
        await markAccountSuccess(next.id);
        await storage.incStats({ ok: true });
      } else if (result.type === 'rateLimited') {
        await markAccountRateLimited(next.id, result.resetAt);
        // Don't mark job failed yet — re-queue by leaving status 'pending' is impossible here
        // since claim already moved it to processing. Mark failed; the customer can retry.
        await server.complete({
          outcome: 'failure',
          jobId: job.id,
          error: 'Rate limited — rotated account, please retry',
        });
        await storage.incStats({ ok: false });
      } else {
        await markAccountError(next.id);
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
      await sleep(8_000); // network backoff
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
