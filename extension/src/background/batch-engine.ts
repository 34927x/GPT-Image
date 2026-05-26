import { api } from '@/shared/api';
import { storage, type Batch, type BatchItem } from '@/shared/storage';
import {
  pickNextAccount,
  markAccountSuccess,
  markAccountRateLimited,
  markAccountError,
  updateAccountCookies,
} from './account-manager';
import { executeIncognito } from './runner';
import { patchStatus, refreshState } from './state';

let abortRequested = false;
let pauseRequested = false;
let running = false;

export function isRunning() {
  return running;
}

export async function startBatch(
  prompts: string[],
  size: Batch['size']
): Promise<void> {
  const items: BatchItem[] = prompts.map((p, i) => ({
    id: `b_${Date.now()}_${i}`,
    prompt: p,
    status: 'pending',
  }));
  const batch: Batch = {
    id: `batch_${Date.now()}`,
    size,
    status: 'running',
    items,
    createdAt: Date.now(),
  };
  await storage.setBatch(batch);
  abortRequested = false;
  pauseRequested = false;
  await refreshState();
  loop();
}

export async function pauseBatch() {
  pauseRequested = true;
  const batch = await storage.getBatch();
  if (batch) {
    batch.status = 'paused';
    await storage.setBatch(batch);
  }
  patchStatus({ status: 'paused' });
}

export async function resumeBatch() {
  const batch = await storage.getBatch();
  if (!batch || batch.status === 'done') return;
  pauseRequested = false;
  abortRequested = false;
  batch.status = 'running';
  await storage.setBatch(batch);
  await refreshState();
  if (!running) loop();
}

export async function stopBatch() {
  abortRequested = true;
  pauseRequested = false;
  const batch = await storage.getBatch();
  if (batch && batch.status !== 'done') {
    batch.status = 'done';
    batch.message = 'Stopped';
    await storage.setBatch(batch);
  }
  patchStatus({ status: 'idle', currentItem: undefined });
}

export async function clearBatch() {
  abortRequested = true;
  pauseRequested = false;
  await storage.setBatch(null);
  patchStatus({ status: 'idle', currentItem: undefined });
  await refreshState();
}

async function loop(): Promise<void> {
  if (running) return;
  running = true;

  while (!abortRequested && !pauseRequested) {
    const batch = await storage.getBatch();
    if (!batch || batch.status !== 'running') break;

    const next = batch.items.find((i) => i.status === 'pending');
    if (!next) {
      // All done!
      batch.status = 'done';
      await storage.setBatch(batch);
      patchStatus({ status: 'idle', currentItem: undefined });
      await refreshState();
      break;
    }

    // Pick an account
    const account = await pickNextAccount();
    if (!account) {
      batch.status = 'paused';
      batch.message = 'All accounts rate-limited or no accounts added.';
      await storage.setBatch(batch);
      patchStatus({
        status: 'paused',
        lastError: batch.message,
      });
      await refreshState();
      // Wait 60s then re-check (rate limits may expire)
      await sleep(60_000);
      if (abortRequested) break;
      pauseRequested = false;
      batch.status = 'running';
      batch.message = undefined;
      await storage.setBatch(batch);
      continue;
    }

    next.status = 'processing';
    next.account = account.label;
    next.startedAt = Date.now();
    await storage.setBatch(batch);
    patchStatus({
      status: 'running',
      currentItem: { id: next.id, prompt: next.prompt, account: account.label },
    });
    await refreshState();

    const { result, refreshedCookies } = await executeIncognito({
      jobId: next.id,
      prompt: next.prompt,
      imageSize: batch.size,
      account,
    });

    if (result.type === 'success') {
      // Save image to disk
      let filename: string | undefined;
      try {
        filename = await downloadImage(
          result.imageDataUrl,
          next.prompt,
          batch.items.indexOf(next) + 1
        );
      } catch (e) {
        console.warn('[bgt] download failed:', e);
      }

      next.status = 'done';
      next.finishedAt = Date.now();
      if (filename) next.filename = filename;

      await markAccountSuccess(account.id);
      if (refreshedCookies?.length) {
        await updateAccountCookies(account.id, refreshedCookies);
      }
      await storage.incStats({ ok: true });
    } else if (result.type === 'rateLimited') {
      // Rotate: mark account limited, leave item PENDING so the loop retries
      // with a different account on the next iteration.
      await markAccountRateLimited(account.id, result.resetAt);
      next.status = 'pending';
      next.account = undefined;
      await storage.incStats({ ok: false });
    } else {
      next.status = 'failed';
      next.error = result.error.slice(0, 280);
      next.finishedAt = Date.now();
      await markAccountError(account.id);
      await storage.incStats({ ok: false });
    }

    await storage.setBatch(batch);
    await refreshState();
    patchStatus({ status: 'running', currentItem: undefined });

    if (abortRequested) break;

    // Cooldown between runs so ChatGPT doesn't think we're spamming
    const settings = await storage.getSettings();
    await sleep(settings.cooldownAfterRunMs);
  }

  running = false;

  if (pauseRequested) {
    patchStatus({ status: 'paused' });
  } else if (abortRequested) {
    patchStatus({ status: 'idle', currentItem: undefined });
  }
}

async function downloadImage(
  dataUrl: string,
  prompt: string,
  index: number
): Promise<string> {
  const settings = await storage.getSettings();
  const slug =
    prompt
      .replace(/[^a-zA-Z0-9]+/g, '-')
      .replace(/-+|^-|-$/g, (m) => (m === '-' ? '-' : ''))
      .slice(0, 40)
      .toLowerCase() || 'image';
  const num = String(index).padStart(3, '0');
  const filename = `${settings.downloadFolder}/${num}-${slug}.png`;

  return new Promise((resolve, reject) => {
    api.downloads.download(
      {
        url: dataUrl,
        filename,
        saveAs: false,
        conflictAction: 'uniquify',
      },
      (downloadId) => {
        if (api.runtime.lastError) {
          reject(new Error(api.runtime.lastError.message));
          return;
        }
        if (!downloadId) {
          reject(new Error('download did not start'));
          return;
        }
        resolve(filename);
      }
    );
  });
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
