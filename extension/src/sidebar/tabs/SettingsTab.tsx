import { useState, useEffect } from 'preact/hooks';
import { Save, Loader2, Check, AlertCircle, Folder } from 'lucide-preact';
import { send } from '@/ui/hooks';
import type { State } from '@/shared/messages';

export function SettingsTab({
  state,
  refresh,
}: {
  state: State;
  refresh: () => Promise<void>;
}) {
  const [folder, setFolder] = useState(state.settings.downloadFolder);
  const [cooldown, setCooldown] = useState(state.settings.cooldownAfterRunMs);
  const [serverUrl, setServerUrl] = useState(state.settings.serverUrl);
  const [token, setToken] = useState(state.settings.workerToken);
  const [saving, setSaving] = useState(false);
  const [pinging, setPinging] = useState(false);
  const [msg, setMsg] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null);

  useEffect(() => {
    setFolder(state.settings.downloadFolder);
    setCooldown(state.settings.cooldownAfterRunMs);
    setServerUrl(state.settings.serverUrl);
    setToken(state.settings.workerToken);
  }, [state.settings]);

  async function save() {
    setSaving(true);
    setMsg(null);
    const res = await send({
      type: 'setSettings',
      patch: {
        downloadFolder: folder.trim() || 'Bulk-GPT',
        cooldownAfterRunMs: Math.max(0, cooldown),
        serverUrl: serverUrl.trim(),
        workerToken: token.trim(),
      },
    });
    if (res.ok) {
      setMsg({ kind: 'ok', text: 'Saved' });
      refresh();
    } else setMsg({ kind: 'err', text: res.error });
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
    <div class="space-y-3">
      {/* Download folder */}
      <div class="card space-y-2">
        <p class="flex items-center gap-1.5 text-[11px] font-semibold text-zinc-300">
          <Folder size={11} />
          Download folder
        </p>
        <input
          class="input"
          placeholder="Bulk-GPT"
          value={folder}
          onInput={(e) => setFolder((e.target as HTMLInputElement).value)}
        />
        <p class="text-[10px] text-zinc-500">
          Saved under <code class="rounded bg-white/5 px-1">Downloads/{folder || 'Bulk-GPT'}/</code>
        </p>
      </div>

      {/* Cooldown */}
      <div class="card space-y-2">
        <p class="text-[11px] font-semibold text-zinc-300">Cooldown between runs</p>
        <div class="flex items-center gap-2">
          <input
            type="number"
            class="input flex-1"
            min={0}
            value={cooldown}
            onInput={(e) =>
              setCooldown(Number((e.target as HTMLInputElement).value) || 0)
            }
          />
          <span class="text-[11px] text-zinc-500">ms</span>
        </div>
        <p class="text-[10px] text-zinc-500">
          Pause between consecutive prompts. Lower = faster, higher = safer.
        </p>
      </div>

      {/* Optional server */}
      <details class="card group" open={!!state.settings.serverUrl}>
        <summary class="cursor-pointer text-[11px] font-semibold text-zinc-300 list-none flex items-center justify-between">
          <span>Server worker mode (optional)</span>
          <span class="text-zinc-500 group-open:rotate-180 transition-transform">▾</span>
        </summary>
        <div class="mt-3 space-y-2">
          <p class="text-[10px] text-zinc-500">
            For when you sell access via the Bulk-GPT website. Leave empty if you only use the extension yourself.
          </p>
          <input
            class="input"
            placeholder="https://bulk-gpt-lemon.vercel.app"
            value={serverUrl}
            onInput={(e) => setServerUrl((e.target as HTMLInputElement).value)}
          />
          <input
            type="password"
            class="input font-mono"
            placeholder="Worker token"
            value={token}
            onInput={(e) => setToken((e.target as HTMLInputElement).value)}
          />
          <button
            class="btn btn-outline w-full"
            onClick={ping}
            disabled={pinging}
          >
            {pinging ? <Loader2 size={12} class="animate-spin" /> : 'Test connection'}
          </button>
        </div>
      </details>

      <button class="btn btn-gradient w-full" onClick={save} disabled={saving}>
        {saving ? <Loader2 size={12} class="animate-spin" /> : <Save size={12} />}
        Save settings
      </button>

      {msg && (
        <div
          class={
            'flex items-center gap-2 rounded-md border p-2 text-[11px] ' +
            (msg.kind === 'ok'
              ? 'border-emerald-500/30 bg-emerald-500/5 text-emerald-300'
              : 'border-rose-500/30 bg-rose-500/5 text-rose-300')
          }
        >
          {msg.kind === 'ok' ? <Check size={12} /> : <AlertCircle size={12} />}
          {msg.text}
        </div>
      )}

      <div class="card text-[10px] text-zinc-400 space-y-1">
        <p class="font-semibold text-zinc-300">Stats</p>
        <div class="flex justify-between">
          <span>Today</span>
          <span class="font-mono text-zinc-200">{state.stats.jobsToday}</span>
        </div>
        <div class="flex justify-between">
          <span>Total</span>
          <span class="font-mono text-zinc-200">{state.stats.jobsTotal}</span>
        </div>
        <div class="flex justify-between">
          <span>Failed today</span>
          <span class="font-mono text-rose-300">{state.stats.failsToday}</span>
        </div>
      </div>
    </div>
  );
}
