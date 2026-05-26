import { useState, useMemo } from 'preact/hooks';
import {
  Play,
  Pause,
  Square,
  Trash2,
  Wand2,
  Check,
  X,
  Loader2,
  Clock,
  Folder,
  AlertCircle,
} from 'lucide-preact';
import { send } from '@/ui/hooks';
import type { State } from '@/shared/messages';
import type { Settings } from '@/shared/storage';

const SIZES: Settings['defaultSize'][] = ['1:1', '16:9', '9:16', '4:3'];

export function GenerateTab({
  state,
  refresh,
}: {
  state: State;
  refresh: () => Promise<void>;
}) {
  const [prompts, setPrompts] = useState('');
  const [size, setSize] = useState<Settings['defaultSize']>(state.settings.defaultSize);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const parsedPrompts = useMemo(() => parsePrompts(prompts), [prompts]);

  const batch = state.batch;
  const isRunning = batch?.status === 'running';
  const isPaused = batch?.status === 'paused';
  const isDone = batch?.status === 'done';
  const hasBatch = !!batch && batch.items.length > 0;

  const stats = useMemo(() => {
    if (!batch) return null;
    const total = batch.items.length;
    const done = batch.items.filter((i) => i.status === 'done').length;
    const failed = batch.items.filter((i) => i.status === 'failed').length;
    const left = total - done - failed;
    return { total, done, failed, left, pct: total ? ((done + failed) / total) * 100 : 0 };
  }, [batch]);

  const accountsCount = state.accounts.length;
  const activeAccounts = state.accounts.filter(
    (a) => !(a.rateLimitedUntil && a.rateLimitedUntil > Date.now())
  ).length;

  async function start() {
    setErr(null);
    if (!parsedPrompts.length) {
      setErr('Paste at least one prompt');
      return;
    }
    if (!accountsCount) {
      setErr('Add at least one account first (Accounts tab)');
      return;
    }
    setBusy(true);
    const r = await send({ type: 'startBatch', prompts: parsedPrompts, size });
    setBusy(false);
    if (!r.ok) setErr(r.error);
    else {
      setPrompts('');
      refresh();
    }
  }

  async function pause() {
    await send({ type: 'pauseBatch' });
    refresh();
  }
  async function resume() {
    await send({ type: 'resumeBatch' });
    refresh();
  }
  async function stop() {
    if (!confirm('Stop current batch?')) return;
    await send({ type: 'stopBatch' });
    refresh();
  }
  async function clear() {
    if (!confirm('Clear batch from view? (Already-downloaded images stay on disk.)')) return;
    await send({ type: 'clearBatch' });
    refresh();
  }

  return (
    <div class="space-y-3">
      {/* Account status banner */}
      {accountsCount === 0 ? (
        <div class="rounded-md border border-rose-500/30 bg-rose-500/5 p-2.5 text-[11px] text-rose-300">
          ⚠️ No accounts yet. Go to <strong>Accounts</strong> tab to capture sessions first.
        </div>
      ) : (
        <div class="flex items-center justify-between rounded-md border border-emerald-500/20 bg-emerald-500/5 px-2.5 py-1.5 text-[10px] text-emerald-300">
          <span>
            {activeAccounts}/{accountsCount} accounts ready
          </span>
          {accountsCount > activeAccounts && (
            <span class="text-amber-300">
              {accountsCount - activeAccounts} cooling down
            </span>
          )}
        </div>
      )}

      {/* Input */}
      {!hasBatch || isDone ? (
        <div class="card space-y-2.5">
          <div class="space-y-1">
            <label class="text-[11px] font-semibold text-zinc-300">Prompts</label>
            <textarea
              class="input min-h-[140px] resize-y font-mono text-xs"
              placeholder={'a cute cat\n\na futuristic city\nneon cyberpunk street'}
              value={prompts}
              onInput={(e) => setPrompts((e.target as HTMLTextAreaElement).value)}
            />
            <p class="text-[10px] text-zinc-500">
              One prompt per line. Use a blank line to separate multi-line prompts.
              {parsedPrompts.length > 0 && (
                <span class="ml-1 text-zinc-300">
                  · <strong>{parsedPrompts.length}</strong> detected
                </span>
              )}
            </p>
          </div>

          <div class="flex items-center gap-2">
            <label class="text-[11px] text-zinc-400">Size</label>
            <select
              class="input flex-1 py-1.5"
              value={size}
              onChange={(e) =>
                setSize((e.target as HTMLSelectElement).value as Settings['defaultSize'])
              }
            >
              {SIZES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <button
            class="btn btn-gradient w-full"
            onClick={start}
            disabled={busy || !parsedPrompts.length || !accountsCount}
          >
            {busy ? (
              <Loader2 size={14} class="animate-spin" />
            ) : (
              <>
                <Wand2 size={14} />
                Generate {parsedPrompts.length || 'images'}
              </>
            )}
          </button>

          {err && (
            <div class="rounded-md border border-rose-500/30 bg-rose-500/5 p-2 text-[11px] text-rose-300 flex items-start gap-2">
              <AlertCircle size={12} class="mt-0.5 shrink-0" />
              {err}
            </div>
          )}
        </div>
      ) : (
        // Active batch — control bar
        <div class="card space-y-2.5">
          {/* Stats */}
          {stats && (
            <div class="grid grid-cols-4 gap-2 text-center">
              <Stat label="Total" value={stats.total} />
              <Stat label="Done" value={stats.done} accent="text-emerald-300" />
              <Stat label="Failed" value={stats.failed} accent="text-rose-300" />
              <Stat label="Left" value={stats.left} accent="text-zinc-300" />
            </div>
          )}

          {/* Progress bar */}
          {stats && (
            <div class="h-1.5 overflow-hidden rounded-full bg-white/5">
              <div
                class="h-full bg-gradient-to-r from-[hsl(263_80%_64%)] to-[hsl(188_95%_55%)] transition-all"
                style={{ width: `${stats.pct}%` }}
              />
            </div>
          )}

          {/* Current */}
          {state.currentItem && (
            <div class="rounded-md border border-amber-500/30 bg-amber-500/5 p-2 text-[11px]">
              <div class="flex items-center gap-1.5 text-amber-300 font-semibold mb-1">
                <Loader2 size={11} class="animate-spin" />
                Generating
                {state.currentItem.account && (
                  <span class="ml-1 rounded bg-amber-500/20 px-1.5 py-0.5 text-[9px]">
                    {state.currentItem.account}
                  </span>
                )}
              </div>
              <p class="line-clamp-2 text-zinc-300">{state.currentItem.prompt}</p>
            </div>
          )}

          {batch?.message && (
            <div class="rounded-md border border-amber-500/30 bg-amber-500/5 p-2 text-[11px] text-amber-300">
              {batch.message}
            </div>
          )}

          {/* Controls */}
          <div class="flex gap-1.5">
            {isRunning && (
              <button class="btn btn-outline flex-1" onClick={pause}>
                <Pause size={12} />
                Pause
              </button>
            )}
            {isPaused && (
              <button class="btn btn-gradient flex-1" onClick={resume}>
                <Play size={12} />
                Resume
              </button>
            )}
            {(isRunning || isPaused) && (
              <button class="btn btn-danger" onClick={stop}>
                <Square size={12} />
                Stop
              </button>
            )}
            {(isDone || (!isRunning && !isPaused)) && (
              <button class="btn btn-outline flex-1" onClick={clear}>
                <Trash2 size={12} />
                Clear
              </button>
            )}
          </div>
        </div>
      )}

      {/* Item list */}
      {batch && batch.items.length > 0 && (
        <div class="space-y-1.5">
          <p class="px-1 text-[10px] uppercase tracking-wider text-zinc-500">
            Queue ({batch.items.length})
          </p>
          <div class="space-y-1 max-h-[320px] overflow-y-auto pr-1">
            {batch.items.map((item) => (
              <ItemRow key={item.id} item={item} />
            ))}
          </div>
        </div>
      )}

      {/* Footer hint */}
      {hasBatch && (
        <div class="rounded-md border border-white/5 bg-white/5 p-2 text-[10px] text-zinc-400 flex items-start gap-1.5">
          <Folder size={11} class="mt-0.5 shrink-0" />
          <span>
            Images saved to{' '}
            <code class="rounded bg-white/10 px-1 text-[9px]">
              Downloads/{state.settings.downloadFolder}/
            </code>
          </span>
        </div>
      )}
    </div>
  );
}

function ItemRow({ item }: { item: State['batch'] extends infer B
  ? B extends { items: infer I }
    ? I extends Array<infer X>
      ? X
      : never
    : never
  : never }) {
  const StatusIcon =
    item.status === 'done'
      ? Check
      : item.status === 'failed'
      ? X
      : item.status === 'processing'
      ? Loader2
      : Clock;

  const color =
    item.status === 'done'
      ? 'text-emerald-400'
      : item.status === 'failed'
      ? 'text-rose-400'
      : item.status === 'processing'
      ? 'text-amber-400'
      : 'text-zinc-500';

  return (
    <div class="flex items-center gap-2 rounded-md border border-white/5 bg-white/[0.02] px-2 py-1.5 text-[11px]">
      <StatusIcon
        size={12}
        class={`${color} ${item.status === 'processing' ? 'animate-spin' : ''} shrink-0`}
      />
      <p
        class={`truncate flex-1 ${item.status === 'pending' ? 'text-zinc-500' : 'text-zinc-200'}`}
        title={item.prompt}
      >
        {item.prompt}
      </p>
      {item.account && (
        <span class="rounded bg-white/5 px-1.5 py-0.5 text-[9px] text-zinc-400">
          {item.account}
        </span>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  accent = 'text-zinc-100',
}: {
  label: string;
  value: number;
  accent?: string;
}) {
  return (
    <div>
      <div class={`text-base font-bold tabular-nums ${accent}`}>{value}</div>
      <div class="text-[9px] uppercase tracking-wider text-zinc-500">{label}</div>
    </div>
  );
}

function parsePrompts(raw: string): string[] {
  // Blank-line separated multi-line prompts, else one per line
  const blocks = raw.split(/\n\s*\n/).map((s) => s.trim()).filter(Boolean);
  if (blocks.length >= 2) return blocks;
  return raw.split('\n').map((s) => s.trim()).filter(Boolean);
}
