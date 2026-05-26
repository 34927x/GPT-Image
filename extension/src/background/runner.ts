import { api } from '@/shared/api';
import type { ContentMessage, ContentResponse } from '@/shared/messages';

const CHATGPT_URL_PREFIX = 'https://chatgpt.com/';

/**
 * Find or open a ChatGPT tab and ensure it's ready to receive a message.
 */
async function getOrCreateChatGPTTab(): Promise<chrome.tabs.Tab> {
  const [existing] = await api.tabs.query({ url: 'https://chatgpt.com/*' });
  if (existing?.id) {
    if (existing.status !== 'complete') {
      await waitForTab(existing.id);
    }
    return existing;
  }
  const tab = await api.tabs.create({ url: CHATGPT_URL_PREFIX, active: false });
  if (!tab.id) throw new Error('Failed to open ChatGPT tab');
  await waitForTab(tab.id);
  return tab;
}

function waitForTab(tabId: number): Promise<void> {
  return new Promise((resolve) => {
    const handler = (id: number, info: chrome.tabs.TabChangeInfo) => {
      if (id === tabId && info.status === 'complete') {
        api.tabs.onUpdated.removeListener(handler);
        resolve();
      }
    };
    api.tabs.onUpdated.addListener(handler);
    // Failsafe: resolve after 30s anyway
    setTimeout(() => {
      api.tabs.onUpdated.removeListener(handler);
      resolve();
    }, 30_000);
  });
}

async function reloadTab(tabId: number): Promise<void> {
  await api.tabs.reload(tabId);
  await waitForTab(tabId);
  // Give the SPA a moment to hydrate
  await new Promise((r) => setTimeout(r, 1500));
}

export async function executePrompt(args: {
  jobId: string;
  prompt: string;
  imageSize: string;
  /** Called after the new account's cookies are in place; reload the tab. */
  needsReload: boolean;
}): Promise<ContentResponse> {
  const tab = await getOrCreateChatGPTTab();
  if (!tab.id) return { type: 'failure', error: 'No tab' };

  if (args.needsReload) {
    await reloadTab(tab.id);
  }

  const msg: ContentMessage = {
    type: 'runPrompt',
    jobId: args.jobId,
    prompt: args.prompt,
    imageSize: args.imageSize,
  };

  try {
    const response = (await api.tabs.sendMessage(tab.id, msg)) as ContentResponse;
    if (!response) return { type: 'failure', error: 'No response from content script' };
    return response;
  } catch (e) {
    return {
      type: 'failure',
      error: e instanceof Error ? e.message : String(e),
    };
  }
}
