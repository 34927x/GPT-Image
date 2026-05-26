import { Power, Zap, Users, AlertCircle, Loader2 } from 'lucide-preact';
import { useState } from 'preact/hooks';
import { send } from '@/ui/hooks';
import type { WorkerState } from '@/shared/messages';

export function OverviewTab({ state, refresh }: { state: WorkerState; refresh: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function toggle() {
    setBusy(true);
    setMsg(null);
    const res = await send({ type: 'setWorkerEnabled', enabled: !state.settings.workerEnabled });
    if (!res.ok) setMsg(res.error);
    setBusy(false);
    refresh();
  }

  const enabled = state.settings.workerEnabled;
  const ready = !!state.settings.serverUrl && !!state.settings.workerToken;
  const hasAccounts = state.accounts.length > 0;
  const canStart = ready && hasAccounts;

  return (
    <div class="space-y-4">
      {/* Worker toggle */}
      <div class="card space-y-3">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm font-semibold">Worker mode</p>
            <p class="text-[11px] text-zinc-400">
              {enabled
                ? state.status === 'processing'
                  ? 'Running a job…'
                  : 'Polling for jobs'
                : 'Click below to start'}
            </p>
          </div>
          <button
            class={enabled ? 'btn btn-danger' : canStart ? 'btn btn-gradient' : 'btn btn-outline'}
            onClick={toggle}
            disabled={busy || (!enabled && !canStart)}
          >
            {busy ? <Loader2 size={14} class="animate-spin" /> : <Power size={14} />}
            {enabled ? 'Stop' : 'Start'}
          </button>
        </div>

        {!ready && (
          <div class="rounded-md border border-amber-500/30 bg-amber-500/5 p-2 text-[11px] text-amber-300">
            Set your server URL and worker token in <strong>Settings</strong> first.
          </div>
        )}
        {ready && !hasAccounts && (
          <div class="rounded-md border border-amber-500/30 bg-amber-500/5 p-2 text-[11px] text-amber-300">
            Add at least one ChatGPT account in <strong>Accounts</strong>.
          </div>
        )}
        {msg && (
          <div class="rounded-md border border-rose-500/30 bg-rose-500/5 p-2 text-[11px] text-rose-300">
            {msg}
          </div>
        )}
      </div>

      {/* Current job */}
      {state.currentJob && (
        <div class="card border-amber-500/30">
          <p class="mb-1 text-[10px] uppercase tracking-wider text-amber-300">Now processing</p>
          <p class="text-xs line-clamp-2">{state.currentJob.prompt}</p>
        </div>
      )}

      {/* Stats grid */}
      <div class="grid grid-cols-2 gap-2">
        <Stat icon={<Zap size={14} />} label="Today" value={state.stats.jobsToday} />
        <Stat icon={<Zap size={14} />} label="Total" value={state.stats.jobsTotal} />
        <Stat
          icon={<Users size={14} />}
          label="Accounts"
          value={state.accounts.length}
        />
        <Stat
          icon={<AlertCircle size={14} />}
          label="Failed today"
          value={state.stats.failsToday}
          accent={state.stats.failsToday > 0 ? 'text-rose-300' : undefined}
        />
      </div>

      {/* Last error */}
      {state.lastError && (
        <div class="card border-rose-500/30 text-[11px] text-rose-300">
          <p class="mb-1 font-semibold">Last error</p>
          <p class="break-words">{state.lastError}</p>
        </div>
      )}
    </div>
  );
}

function Stat({
  icon,
  label,
  value,
  accent,
}: {
  icon: preact.ComponentChildren;
  label: string;
  value: number;
  accent?: string;
}) {
  return (
    <div class="card flex flex-col gap-1 p-3">
      <div class="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-zinc-400">
        {icon}
        {label}
      </div>
      <div class={`text-lg font-bold tabular-nums ${accent ?? ''}`}>{value}</div>
    </div>
  );
}
