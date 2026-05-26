import { useState } from 'preact/hooks';
import { Wand2, Users, Settings as SettingsIcon } from 'lucide-preact';
import { useWorkerState } from '@/ui/hooks';
import { Logo } from '@/ui/Logo';
import { GenerateTab } from './tabs/GenerateTab';
import { AccountsTab } from './tabs/AccountsTab';
import { SettingsTab } from './tabs/SettingsTab';

type Tab = 'generate' | 'accounts' | 'settings';

export function App() {
  const [tab, setTab] = useState<Tab>('generate');
  const { state, loading, refresh } = useWorkerState();

  return (
    <div class="flex h-full flex-col">
      <header class="flex items-center justify-between border-b border-white/5 px-4 py-3 backdrop-blur-md">
        <Logo size="sm" />
        <StatusPill state={state} />
      </header>

      <nav class="flex border-b border-white/5">
        <TabButton active={tab === 'generate'} onClick={() => setTab('generate')} icon={<Wand2 size={14} />}>
          Generate
        </TabButton>
        <TabButton active={tab === 'accounts'} onClick={() => setTab('accounts')} icon={<Users size={14} />}>
          Accounts
          {state && state.accounts.length > 0 && (
            <span class="ml-1 rounded-full bg-white/10 px-1.5 py-0.5 text-[9px] tabular-nums">
              {state.accounts.length}
            </span>
          )}
        </TabButton>
        <TabButton active={tab === 'settings'} onClick={() => setTab('settings')} icon={<SettingsIcon size={14} />}>
          Settings
        </TabButton>
      </nav>

      <main class="flex-1 overflow-y-auto p-3">
        {loading || !state ? (
          <div class="flex h-full items-center justify-center text-xs text-zinc-500">Loading…</div>
        ) : tab === 'generate' ? (
          <GenerateTab state={state} refresh={refresh} />
        ) : tab === 'accounts' ? (
          <AccountsTab state={state} refresh={refresh} />
        ) : (
          <SettingsTab state={state} refresh={refresh} />
        )}
      </main>

      <footer class="border-t border-white/5 px-4 py-2 text-center text-[10px] text-zinc-500">
        Bulk-GPT v4 · TurabCoder
      </footer>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  children,
}: {
  active: boolean;
  onClick: () => void;
  icon: preact.ComponentChildren;
  children: preact.ComponentChildren;
}) {
  return (
    <button
      class={
        'flex flex-1 items-center justify-center gap-1.5 px-3 py-2.5 text-xs font-semibold transition-colors ' +
        (active
          ? 'text-white border-b-2 border-[hsl(263_80%_64%)]'
          : 'text-zinc-400 hover:text-white border-b-2 border-transparent')
      }
      onClick={onClick}
    >
      {icon}
      {children}
    </button>
  );
}

function StatusPill({ state }: { state: ReturnType<typeof useWorkerState>['state'] }) {
  if (!state) return <span class="badge badge-muted">…</span>;
  if (state.status === 'running')
    return (
      <span class="badge badge-warning">
        <span class="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
        Generating
      </span>
    );
  if (state.status === 'paused') return <span class="badge badge-warning">Paused</span>;
  if (state.status === 'error') return <span class="badge badge-danger">Error</span>;
  return <span class="badge badge-muted">Idle</span>;
}
