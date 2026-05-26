import { render } from 'preact';
import { ExternalLink, PanelRight } from 'lucide-preact';
import { Logo } from '@/ui/Logo';
import { api } from '@/shared/api';
import { useWorkerState } from '@/ui/hooks';
import '@/styles.css';

function Popup() {
  const { state } = useWorkerState();

  const status = state?.status ?? 'idle';
  const accountsCount = state?.accounts.length ?? 0;
  const batch = state?.batch;

  function openSidebar() {
    if (api.sidePanel) {
      api.windows.getCurrent().then((w) => {
        if (w.id) api.sidePanel.open({ windowId: w.id });
        window.close();
      });
    } else {
      api.tabs.create({ url: api.runtime.getURL('sidebar.html') });
      window.close();
    }
  }

  return (
    <div class="p-3 space-y-3">
      <div class="flex items-center justify-between">
        <Logo size="sm" />
        <span class={`badge ${status === 'running' ? 'badge-warning' : 'badge-muted'}`}>
          {status === 'running' ? 'Generating' : status === 'paused' ? 'Paused' : 'Idle'}
        </span>
      </div>

      <div class="card space-y-1.5 text-xs">
        <div class="flex justify-between">
          <span class="text-zinc-400">Accounts</span>
          <span class="font-semibold tabular-nums">{accountsCount}</span>
        </div>
        {batch && batch.items.length > 0 && (
          <>
            <div class="flex justify-between">
              <span class="text-zinc-400">Done</span>
              <span class="font-semibold tabular-nums text-emerald-300">
                {batch.items.filter((i) => i.status === 'done').length}/{batch.items.length}
              </span>
            </div>
          </>
        )}
        <div class="flex justify-between">
          <span class="text-zinc-400">Today</span>
          <span class="font-semibold tabular-nums">{state?.stats.jobsToday ?? 0}</span>
        </div>
      </div>

      <button class="btn btn-gradient w-full" onClick={openSidebar}>
        <PanelRight size={14} />
        Open dashboard
      </button>

      <button
        class="btn btn-outline w-full"
        onClick={() => {
          api.tabs.create({ url: 'https://chatgpt.com' });
          window.close();
        }}
      >
        <ExternalLink size={14} />
        chatgpt.com
      </button>

      <p class="text-center text-[10px] text-zinc-500">Bulk-GPT v4 · TurabCoder</p>
    </div>
  );
}

render(<Popup />, document.getElementById('app')!);
