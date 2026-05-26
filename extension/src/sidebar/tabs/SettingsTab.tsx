import { useState, useEffect } from 'preact/hooks';
import { Save, Loader2, CheckCircle2, AlertCircle } from 'lucide-preact';
import { send } from '@/ui/hooks';
import type { WorkerState } from '@/shared/messages';

export function SettingsTab({
  state,
  refresh,
}: {
  state: WorkerState;
  refresh: () => Promise<void>;
}) {
  const [serverUrl, setServerUrl] = useState(state.settings.serverUrl);
  const [token, setToken] = useState(state.settings.workerToken);
  const [label, setLabel] = useState(state.settings.workerLabel);
  const [pollInterval, setPollInterval] = useState(state.settings.pollIntervalMs);
  const [cooldown, setCooldown] = useState(state.settings.cooldownAfterRunMs);
  const [saving, setSaving] = useState(false);
  const [pinging, setPinging] = useState(false);
  const [msg, setMsg] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null);

  // Sync if state changes externally
  useEffect(() => {
    setServerUrl(state.settings.serverUrl);
    setToken(state.settings.workerToken);
    setLabel(state.settings.workerLabel);
    setPollInterval(state.settings.pollIntervalMs);
    setCooldown(state.settings.cooldownAfterRunMs);
  }, [state.settings]);

  async function save() {
    setSaving(true);
    setMsg(null);
    const res = await send({
      type: 'setSettings',
      patch: {
        serverUrl: serverUrl.trim(),
        workerToken: token.trim(),
        workerLabel: label.trim(),
        pollIntervalMs: Math.max(1000, pollInterval),
        cooldownAfterRunMs: Math.max(0, cooldown),
      },
    });
    if (res.ok) {
      setMsg({ kind: 'ok', text: 'Saved' });
      refresh();
    } else {
      setMsg({ kind: 'err', text: res.error });
    }
    setSaving(false);
  }

  async function ping() {
    setPinging(true);
    setMsg(null);
    const res = await send({ type: 'pingServer' });
    setMsg(res.ok ? { kind: 'ok', text: 'Connected!' } : { kind: 'err', text: res.error });
    setPinging(false);
  }

  return (
    <div class="space-y-4">
      <div class="card space-y-3">
        <p class="text-xs font-semibold uppercase tracking-wider text-zinc-400">
          Server
        </p>
        <div class="space-y-1.5">
          <label class="text-[11px] text-zinc-400">Server URL</label>
          <input
            class="input"
            placeholder="https://bulk-gpt.vercel.app"
            value={serverUrl}
            onInput={(e) => setServerUrl((e.target as HTMLInputElement).value)}
          />
        </div>
        <div class="space-y-1.5">
          <label class="text-[11px] text-zinc-400">Worker token</label>
          <input
            type="password"
            class="input font-mono"
            placeholder="From Vercel env: WORKER_TOKEN"
            value={token}
            onInput={(e) => setToken((e.target as HTMLInputElement).value)}
          />
        </div>
        <div class="space-y-1.5">
          <label class="text-[11px] text-zinc-400">Worker label (optional)</label>
          <input
            class="input"
            placeholder="My Laptop"
            value={label}
            onInput={(e) => setLabel((e.target as HTMLInputElement).value)}
          />
        </div>
      </div>

      <div class="card space-y-3">
        <p class="text-xs font-semibold uppercase tracking-wider text-zinc-400">
          Timing
        </p>
        <div class="grid grid-cols-2 gap-2">
          <div class="space-y-1.5">
            <label class="text-[11px] text-zinc-400">Poll interval (ms)</label>
            <input
              type="number"
              class="input"
              min={1000}
              value={pollInterval}
              onInput={(e) =>
                setPollInterval(Number((e.target as HTMLInputElement).value) || 5000)
              }
            />
          </div>
          <div class="space-y-1.5">
            <label class="text-[11px] text-zinc-400">Cooldown (ms)</label>
            <input
              type="number"
              class="input"
              min={0}
              value={cooldown}
              onInput={(e) =>
                setCooldown(Number((e.target as HTMLInputElement).value) || 0)
              }
            />
          </div>
        </div>
      </div>

      <div class="flex gap-2">
        <button class="btn btn-gradient flex-1" onClick={save} disabled={saving}>
          {saving ? <Loader2 size={14} class="animate-spin" /> : <Save size={14} />}
          Save
        </button>
        <button class="btn btn-outline" onClick={ping} disabled={pinging}>
          {pinging ? <Loader2 size={14} class="animate-spin" /> : 'Test'}
        </button>
      </div>

      {msg && (
        <div
          class={
            'flex items-center gap-2 rounded-md border p-2 text-[11px] ' +
            (msg.kind === 'ok'
              ? 'border-emerald-500/30 bg-emerald-500/5 text-emerald-300'
              : 'border-rose-500/30 bg-rose-500/5 text-rose-300')
          }
        >
          {msg.kind === 'ok' ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
          {msg.text}
        </div>
      )}

      <div class="card text-[11px] text-zinc-400 space-y-1">
        <p>
          <span class="font-semibold text-zinc-300">Worker ID:</span>{' '}
          <span class="font-mono">{state.workerId}</span>
        </p>
        <p>
          Settings sync to <code class="rounded bg-white/5 px-1">storage.local</code>.
          Keep your token private — anyone with it can submit fake images to your queue.
        </p>
      </div>
    </div>
  );
}
