import { api } from '@/shared/api';
import {
  injectIntoStore,
  clearStore,
  captureFromStore,
} from '@/shared/cookies';
import type { Account } from '@/shared/storage';
import type { ContentMessage, ContentResponse } from '@/shared/messages';

const CHATGPT_URL = 'https://chatgpt.com/';
const TAB_LOAD_TIMEOUT_MS = 45_000;

/**
 * Orchestrates one job in an incognito window:
 *   1. Open a new incognito window (its own cookie store)
 *   2. Inject the account's cookies
 *   3. Navigate to chatgpt.com
 *   4. Send the prompt (via content script)
 *   5. Wait for the image
 *   6. Capture refreshed cookies from the store
 *   7. Close the window
 */
export async function executeIncognito(args: {
  jobId: string;
  prompt: string;
  imageSize: string;
  account: Account;
}): Promise<{
  result: ContentResponse;
  refreshedCookies?: Account['cookies'];
}> {
  // 1) Open incognito window
  const win = await api.windows.create({
    incognito: true,
    url: 'about:blank',
    focused: false,
  });
  const tabId = win.tabs?.[0]?.id;
  if (!tabId) {
    return { result: { type: 'failure', error: 'Could not open incognito window' } };
  }

  let storeId: string | undefined;

  try {
    // Get the cookie store for this incognito window
    const tab = await api.tabs.get(tabId);
    storeId = (tab as chrome.tabs.Tab & { cookieStoreId?: string }).cookieStoreId;

    // Fallback: derive from windowId if Chrome doesn't expose cookieStoreId on Tab
    if (!storeId) {
      const stores = await api.cookies.getAllCookieStores();
      const wId = win.id;
      const match = stores.find((s) => wId !== undefined && s.tabIds.includes(tabId));
      storeId = match?.id;
    }

    if (!storeId) {
      return {
        result: {
          type: 'failure',
          error:
            'Extension not allowed in incognito. Enable it in chrome://extensions',
        },
      };
    }

    // 2) Inject cookies into this incognito session
    await clearStore(storeId);
    const { injected } = await injectIntoStore(args.account.cookies, storeId);
    if (injected === 0) {
      return {
        result: { type: 'failure', error: 'No cookies could be injected' },
      };
    }

    // 3) Navigate the tab to chatgpt.com
    await api.tabs.update(tabId, { url: CHATGPT_URL });
    await waitForTabLoad(tabId);

    // 4-5) Send the prompt and wait for image
    const msg: ContentMessage = {
      type: 'runPrompt',
      jobId: args.jobId,
      prompt: args.prompt,
      imageSize: args.imageSize,
    };

    const response = (await api.tabs.sendMessage(tabId, msg).catch(
      (e) =>
        ({ type: 'failure', error: 'Tab message: ' + (e as Error).message } as ContentResponse)
    )) as ContentResponse;

    // 6) Capture refreshed cookies (if successful)
    let refreshedCookies: Account['cookies'] | undefined;
    if (response.type === 'success') {
      try {
        refreshedCookies = await captureFromStore(storeId);
      } catch {
        /* non-fatal */
      }
    }

    return { result: response, refreshedCookies };
  } catch (e) {
    return {
      result: {
        type: 'failure',
        error: e instanceof Error ? e.message : String(e),
      },
    };
  } finally {
    // 7) Always close the window
    try {
      if (win.id) await api.windows.remove(win.id);
    } catch {
      /* tab may already be gone */
    }
  }
}

function waitForTabLoad(tabId: number): Promise<void> {
  return new Promise((resolve) => {
    const handler = (id: number, info: chrome.tabs.TabChangeInfo) => {
      if (id === tabId && info.status === 'complete') {
        api.tabs.onUpdated.removeListener(handler);
        // small grace period for SPA hydration
        setTimeout(resolve, 1500);
      }
    };
    api.tabs.onUpdated.addListener(handler);
    setTimeout(() => {
      api.tabs.onUpdated.removeListener(handler);
      resolve();
    }, TAB_LOAD_TIMEOUT_MS);
  });
}
