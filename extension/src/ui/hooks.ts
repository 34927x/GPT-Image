import { useEffect, useState, useCallback } from 'preact/hooks';
import { api } from '@/shared/api';
import type { UIMessage, BackgroundResponse, WorkerState } from '@/shared/messages';

export async function send(msg: UIMessage): Promise<BackgroundResponse> {
  return new Promise((resolve) => {
    api.runtime.sendMessage(msg, (res: BackgroundResponse) => {
      if (api.runtime.lastError) {
        resolve({ ok: false, error: api.runtime.lastError.message ?? 'send failed' });
        return;
      }
      resolve(res ?? { ok: false, error: 'No response' });
    });
  });
}

export function useWorkerState(): {
  state: WorkerState | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
} {
  const [state, setState] = useState<WorkerState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const res = await send({ type: 'getState' });
    if (res.ok) {
      setState(res.data as WorkerState);
      setError(null);
    } else setError(res.error);
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
    const handler = (msg: { type?: string; state?: WorkerState }) => {
      if (msg?.type === 'stateUpdate' && msg.state) setState(msg.state);
    };
    api.runtime.onMessage.addListener(handler);
    return () => api.runtime.onMessage.removeListener(handler);
  }, [refresh]);

  return { state, loading, error, refresh };
}
