import { render } from 'preact';
import { ExternalLink, Settings as SettingsIcon, PanelRight } from 'lucide-preact';
import { Logo } from '@/ui/Logo';
import { api } from '@/shared/api';
import { useWorkerState } from '@/ui/hooks';
import '@/styles.css';

function Popup() {
  const { state } = useWorkerState();

  const enabled = state?.settings.workerEnabled ?? false;
  const status = state?.status ?? 'idle';
  const accountsCount = state?.accounts.length ?? 0;

  const statusBadge =
    status === 'processing'
      ? 'badge-warning'
      : status === 'polling' || status === 'idle'
      ? enabled
        ? 'badge-success'
        : 'badge-muted'
      : 'badge-danger';

  const statusText = !enabled ? 'Off' : status === 'processing' ? 'Working' : status === 'polling' ? 'Online' : status;

  function openSidebar() {
    if (api.sidePanel) {
      // requires a user gesture in MV3
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
        <span class={`badge ${statusBadge}`}>{statusText}</span>
      </div>

      <div class="card space-y-1.5">
        <div class="flex justify-between text-xs">
          <span class="text-zinc-400">Accounts</span>
          <span class="font-semibold">{accountsCount}</span>
        </div>
        <div class="flex justify-between text-xs">
          <span class="text-zinc-400">Jobs today</span>
          <span class="font-semibold">{state?.stats.jobsToday ?? 0}</span>
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
        Open chatgpt.com
      </button>

      <p class="text-center text-[10px] text-zinc-500">Bulk-GPT v4 · TurabCoder</p>
    </div>
  );
}

render(<Popup />, document.getElementById('app')!);
