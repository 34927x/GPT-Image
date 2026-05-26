import { useState } from 'preact/hooks';
import { Plus, Trash2, RefreshCw, Check, Loader2, ExternalLink } from 'lucide-preact';
import { send } from '@/ui/hooks';
import type { WorkerState } from '@/shared/messages';
import { api } from '@/shared/api';

export function AccountsTab({
  state,
  refresh,
}: {
  state: WorkerState;
  refresh: () => Promise<void>;
}) {
  const [showAdd, setShowAdd] = useState(false);
  const [label, setLabel] = useState('');
  const [busy, setBusy] = useState<string | null>(null); // id of busy operation
  const [msg, setMsg] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null);

  async function capture() {
    setBusy('capture');
    setMsg(null);
    const res = await send({ type: 'captureCurrentSession', label });
    setBusy(null);
    if (res.ok) {
      setMsg({ kind: 'ok', text: 'Captured ✓' });
      setLabel('');
      setShowAdd(false);
    } else {
      setMsg({ kind: 'err', text: res.error });
    }
    refresh();
  }

  async function refreshCookies(id: string) {
    setBusy(`refresh-${id}`);
    setMsg(null);
    const res = await send({ type: 'refreshAccountCookies', id });
    setBusy(null);
    if (res.ok) setMsg({ kind: 'ok', text: 'Cookies refreshed ✓' });
    else setMsg({ kind: 'err', text: res.error });
    refresh();
  }

  async function remove(id: string) {
    if (!confirm('Remove this account?')) return;
    await send({ type: 'removeAccount', id });
    refresh();
  }

  function openChatGPT() {
    api.tabs.create({ url: 'https://chatgpt.com' });
  }

  const now = Date.now();

  return (
    <div class="space-y-3">
      {!showAdd ? (
        <button class="btn btn-gradient w-full" onClick={() => setShowAdd(true)}>
          <Plus size={14} />
          Capture session
        </button>
      ) : (
        <div class="card space-y-3">
          <div class="text-xs text-zinc-300">
            <p class="mb-2">
              Step 1: Open{' '}
              <button class="text-[hsl(188_95%_55%)] underline inline-flex items-center gap-1" onClick={openChatGPT}>
                chatgpt.com <ExternalLink size={10} />
              </button>{' '}
              and log in.
            </p>
            <p>Step 2: Come back and click Capture below.</p>
          </div>
          <input
            class="input"
            placeholder="Label (e.g., Free account 1)"
            value={label}
            onInput={(e) => setLabel((e.target as HTMLInputElement).value)}
          />
          <div class="flex gap-2">
            <button
              class="btn btn-gradient flex-1"
              onClick={capture}
              disabled={busy === 'capture'}
            >
              {busy === 'capture' ? <Loader2 size={14} class="animate-spin" /> : <Check size={14} />}
              Capture
            </button>
            <button class="btn btn-outline" onClick={() => setShowAdd(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {msg && (
        <div
          class={
            'rounded-md border p-2 text-[11px] ' +
            (msg.kind === 'ok'
              ? 'border-emerald-500/30 bg-emerald-500/5 text-emerald-300'
              : 'border-rose-500/30 bg-rose-500/5 text-rose-300')
          }
        >
          {msg.text}
        </div>
      )}

      {state.accounts.length === 0 ? (
        <div class="rounded-lg border border-dashed border-white/10 py-12 text-center text-xs text-zinc-500">
          No accounts yet.
          <br />
          Capture your first session above.
        </div>
      ) : (
        <div class="space-y-2">
          {state.accounts.map((acc) => {
            const limited = !!(acc.rateLimitedUntil && acc.rateLimitedUntil > now);
            const ageHours = Math.floor((now - acc.capturedAt) / 3_600_000);
            return (
              <div key={acc.id} class="card p-3 space-y-2">
                <div class="flex items-start gap-2">
                  <div
                    class={
                      'mt-1 h-2 w-2 shrink-0 rounded-full ' +
                      (limited ? 'bg-amber-400' : 'bg-emerald-400')
                    }
                  />
                  <div class="min-w-0 flex-1">
                    <p class="truncate text-sm font-semibold">{acc.label}</p>
                    <p class="text-[10px] text-zinc-500">
                      {acc.cookies.length} cookies · captured{' '}
                      {ageHours < 1 ? 'just now' : `${ageHours}h ago`}
                      {limited && acc.rateLimitedUntil && (
                        <span class="ml-1 text-amber-300">
                          · limited {formatLeft(acc.rateLimitedUntil - now)}
                        </span>
                      )}
                    </p>
                  </div>
                </div>
                <div class="flex gap-1.5">
                  <button
                    class="btn btn-outline text-[11px] flex-1"
                    onClick={() => refreshCookies(acc.id)}
                    disabled={busy === `refresh-${acc.id}`}
                    title="Replace cookies with the current chatgpt.com session"
                  >
                    {busy === `refresh-${acc.id}` ? (
                      <Loader2 size={11} class="animate-spin" />
                    ) : (
                      <RefreshCw size={11} />
                    )}
                    Refresh
                  </button>
                  <button
                    class="btn btn-danger text-[11px]"
                    onClick={() => remove(acc.id)}
                    title="Remove account"
                  >
                    <Trash2 size={11} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <p class="rounded-lg border border-white/5 bg-white/5 p-3 text-[11px] text-zinc-400">
        💡 Each job runs in a fresh incognito window with the selected account&apos;s
        cookies. Cookies auto-refresh after every successful run.
      </p>
    </div>
  );
}

function formatLeft(ms: number): string {
  const m = Math.floor(ms / 60000);
  if (m < 1) return '<1m left';
  if (m < 60) return `${m}m left`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m left`;
}
