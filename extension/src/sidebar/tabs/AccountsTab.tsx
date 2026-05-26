import { useState } from 'preact/hooks';
import { Plus, Trash2, Check, AlertCircle, Loader2 } from 'lucide-preact';
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
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null);

  async function capture() {
    setBusy(true);
    setMsg(null);
    const res = await send({ type: 'captureCurrentSession', label });
    if (res.ok) {
      setMsg({ kind: 'ok', text: 'Captured!' });
      setLabel('');
      setShowAdd(false);
    } else {
      setMsg({ kind: 'err', text: res.error });
    }
    setBusy(false);
    refresh();
  }

  async function remove(id: string) {
    if (!confirm('Remove this account?')) return;
    await send({ type: 'removeAccount', id });
    refresh();
  }

  async function switchTo(id: string) {
    await send({ type: 'switchToAccount', id });
    refresh();
  }

  function openChatGPT() {
    api.tabs.create({ url: 'https://chatgpt.com' });
  }

  const now = Date.now();

  return (
    <div class="space-y-3">
      {/* Add account */}
      {!showAdd ? (
        <button class="btn btn-gradient w-full" onClick={() => setShowAdd(true)}>
          <Plus size={14} />
          Capture current session
        </button>
      ) : (
        <div class="card space-y-3">
          <p class="text-xs">
            Make sure you&apos;re logged in to{' '}
            <button class="text-[hsl(188_95%_55%)] underline" onClick={openChatGPT}>
              chatgpt.com
            </button>{' '}
            in this browser.
          </p>
          <input
            class="input"
            placeholder="Label (e.g., Work account)"
            value={label}
            onInput={(e) => setLabel((e.target as HTMLInputElement).value)}
          />
          <div class="flex gap-2">
            <button
              class="btn btn-gradient flex-1"
              onClick={capture}
              disabled={busy}
            >
              {busy ? <Loader2 size={14} class="animate-spin" /> : <Check size={14} />}
              Capture
            </button>
            <button class="btn btn-outline" onClick={() => setShowAdd(false)}>
              Cancel
            </button>
          </div>
          {msg && (
            <p
              class={
                'text-[11px] ' +
                (msg.kind === 'ok' ? 'text-emerald-300' : 'text-rose-300')
              }
            >
              {msg.text}
            </p>
          )}
        </div>
      )}

      {/* List */}
      {state.accounts.length === 0 ? (
        <div class="rounded-lg border border-dashed border-white/10 py-12 text-center text-xs text-zinc-500">
          No accounts yet.
          <br />
          Capture your first session above.
        </div>
      ) : (
        <div class="space-y-2">
          {state.accounts.map((acc, i) => {
            const limited = !!(acc.rateLimitedUntil && acc.rateLimitedUntil > now);
            const isActive = i === state.activeIdx;
            return (
              <div
                key={acc.id}
                class={
                  'card flex items-center gap-3 p-3 ' +
                  (isActive ? 'border-[hsl(263_80%_64%/0.5)]' : '')
                }
              >
                <div
                  class={
                    'h-2 w-2 shrink-0 rounded-full ' +
                    (limited
                      ? 'bg-amber-400'
                      : isActive
                      ? 'bg-emerald-400'
                      : 'bg-zinc-600')
                  }
                />
                <div class="min-w-0 flex-1">
                  <p class="truncate text-sm font-semibold">{acc.label}</p>
                  <p class="text-[10px] text-zinc-500">
                    {acc.cookies.length} cookies
                    {limited && acc.rateLimitedUntil && (
                      <>
                        {' · '}
                        <span class="text-amber-300">
                          limited {formatLeft(acc.rateLimitedUntil - now)}
                        </span>
                      </>
                    )}
                  </p>
                </div>
                <div class="flex gap-1">
                  {!isActive && (
                    <button
                      class="btn btn-ghost text-[10px]"
                      onClick={() => switchTo(acc.id)}
                      title="Switch"
                    >
                      Use
                    </button>
                  )}
                  {isActive && (
                    <span class="badge badge-success">Active</span>
                  )}
                  <button
                    class="btn btn-ghost"
                    onClick={() => remove(acc.id)}
                    title="Remove"
                  >
                    <Trash2 size={12} class="text-rose-300" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <p class="rounded-lg border border-white/5 bg-white/5 p-3 text-[11px] text-zinc-400">
        💡 Capturing reads the cookies for chatgpt.com from this browser. Add multiple
        accounts to enable rotation when one hits a rate limit.
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
