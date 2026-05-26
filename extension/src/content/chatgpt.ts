/**
 * Bulk-GPT content script — runs on chatgpt.com.
 *
 * Receives a `runPrompt` message, finds the input, sends the prompt, waits
 * for the generated image, and returns it as a data URL so the background
 * script can ship it to the server.
 */

import type { ContentMessage, ContentResponse } from '@/shared/messages';

const PROMPT_SELECTORS = [
  '#prompt-textarea',
  'div[contenteditable="true"]',
  '[role="textbox"]',
  'textarea:not([hidden])',
];

const SEND_BUTTON_SELECTORS = [
  'button[data-testid="send-button"]',
  'button[aria-label*="Send"]',
  'button[aria-label*="send"]',
];

const STOP_BUTTON_SELECTORS = [
  'button[data-testid="stop-button"]',
  'button[aria-label*="Stop"]',
  'button[aria-label*="stop"]',
];

const IMAGE_SELECTORS = [
  'img[src*="oaidalle"]',
  'img[src*="dalle"]',
  'img[alt*="Generated"]',
  'img[src*="files.oaiusercontent.com"]',
];

const RATE_LIMIT_PATTERNS = [
  /you've reached the limit/i,
  /rate.?limit/i,
  /too many requests/i,
  /resets in/i,
];

const DEFAULT_TIMEOUT_MS = 120_000;

let aborted = false;

const api = chrome;

api.runtime.onMessage.addListener((rawMsg, _sender, sendResponse) => {
  const msg = rawMsg as ContentMessage;
  if (msg.type === 'abort') {
    aborted = true;
    sendResponse({ type: 'failure', error: 'Aborted' } satisfies ContentResponse);
    return false;
  }
  if (msg.type === 'runPrompt') {
    aborted = false;
    runPrompt(msg.prompt)
      .then(sendResponse)
      .catch((e: unknown) =>
        sendResponse({
          type: 'failure',
          error: e instanceof Error ? e.message : String(e),
        } satisfies ContentResponse)
      );
    return true; // async
  }
  return false;
});

async function runPrompt(prompt: string): Promise<ContentResponse> {
  await dismissPopups();

  const input = await waitForElement(PROMPT_SELECTORS, 15_000);
  if (!input) return { type: 'failure', error: 'Prompt input not found' };

  await fillInput(input as HTMLElement, prompt);
  await sleep(500);
  if (aborted) return { type: 'failure', error: 'Aborted' };

  const sendBtn = querySelectors(SEND_BUTTON_SELECTORS);
  if (sendBtn) {
    (sendBtn as HTMLButtonElement).click();
  } else {
    input.dispatchEvent(
      new KeyboardEvent('keydown', {
        key: 'Enter',
        code: 'Enter',
        keyCode: 13,
        which: 13,
        bubbles: true,
        cancelable: true,
      })
    );
  }

  const ok = await waitForGeneration(DEFAULT_TIMEOUT_MS);
  if (aborted) return { type: 'failure', error: 'Aborted' };

  if (ok === 'rateLimited') return { type: 'rateLimited' };
  if (!ok) return { type: 'failure', error: 'Generation timed out' };

  await sleep(1500);
  const imgEl = lastImage();
  if (!imgEl) return { type: 'failure', error: 'Image element not found after generation' };

  const dataUrl = await imageToDataUrl(imgEl);
  if (!dataUrl) return { type: 'failure', error: 'Failed to read image' };

  return { type: 'success', imageDataUrl: dataUrl };
}

// ============ DOM helpers ============

function querySelectors<T extends Element = Element>(selectors: string[]): T | null {
  for (const sel of selectors) {
    const el = document.querySelector<T>(sel);
    if (el) return el;
  }
  return null;
}

async function waitForElement(
  selectors: string[],
  timeoutMs: number
): Promise<Element | null> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (aborted) return null;
    const el = querySelectors(selectors);
    if (el) return el;
    await sleep(300);
  }
  return null;
}

async function fillInput(input: HTMLElement, value: string): Promise<void> {
  if (input instanceof HTMLTextAreaElement) {
    setReactValue(input, value);
  } else if (input.isContentEditable) {
    input.focus();
    input.textContent = value;
    input.dispatchEvent(new InputEvent('input', { bubbles: true, data: value }));
  } else if (input instanceof HTMLInputElement) {
    setReactValue(input, value);
  }
}

function setReactValue(el: HTMLInputElement | HTMLTextAreaElement, value: string): void {
  const proto = Object.getPrototypeOf(el);
  const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
  if (setter) setter.call(el, value);
  else el.value = value;
  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
}

async function dismissPopups(): Promise<void> {
  const buttons = [
    'button:has-text("Got it")',
    'button:has-text("Okay")',
    'button:has-text("Continue")',
    '[aria-label="Close"]',
  ];
  for (const sel of buttons) {
    try {
      const btn = document.querySelector(sel) as HTMLElement | null;
      if (btn?.offsetParent) btn.click();
    } catch {
      /* CSS :has-text isn't standard; fall through */
    }
  }
  // Plain text-content scan
  document.querySelectorAll('button').forEach((b) => {
    const t = b.textContent?.trim().toLowerCase() ?? '';
    if (
      ['got it', 'okay', 'okay, let’s go', 'continue', 'dismiss', 'close'].includes(t) &&
      (b as HTMLElement).offsetParent
    ) {
      b.click();
    }
  });
}

/**
 * Wait for the model to finish:
 *  1. Stop button appears (generation started)
 *  2. Stop button disappears (generation finished)
 *  3. Image appears (final check)
 */
async function waitForGeneration(timeoutMs: number): Promise<true | 'rateLimited' | false> {
  const deadline = Date.now() + timeoutMs;

  // Phase 1: wait for stop button
  let started = false;
  while (Date.now() < deadline) {
    if (aborted) return false;
    if (querySelectors(STOP_BUTTON_SELECTORS)) {
      started = true;
      break;
    }
    if (isRateLimited()) return 'rateLimited';
    await sleep(400);
  }
  if (!started) return false;

  // Phase 2: wait for stop button to disappear
  while (Date.now() < deadline) {
    if (aborted) return false;
    if (!querySelectors(STOP_BUTTON_SELECTORS)) break;
    if (isRateLimited()) return 'rateLimited';
    await sleep(700);
  }

  // Phase 3: confirm image appears
  for (let i = 0; i < 6; i++) {
    if (aborted) return false;
    if (lastImage()) return true;
    await sleep(700);
  }
  if (isRateLimited()) return 'rateLimited';
  return false;
}

function isRateLimited(): boolean {
  const text = document.body.innerText;
  return RATE_LIMIT_PATTERNS.some((re) => re.test(text));
}

function lastImage(): HTMLImageElement | null {
  const imgs = document.querySelectorAll<HTMLImageElement>(IMAGE_SELECTORS.join(','));
  for (let i = imgs.length - 1; i >= 0; i--) {
    const img = imgs[i];
    if (img.complete && img.naturalWidth > 0 && !img.src.startsWith('blob:')) {
      return img;
    }
  }
  return null;
}

async function imageToDataUrl(img: HTMLImageElement): Promise<string | null> {
  // Prefer fetching the source URL — works around canvas tainting for cross-origin
  // images that have CORS headers.
  try {
    const res = await fetch(img.src);
    if (!res.ok) throw new Error('fetch failed');
    const blob = await res.blob();
    return await blobToDataUrl(blob);
  } catch {
    // Fallback: try canvas
    try {
      const canvas = document.createElement('canvas');
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const ctx = canvas.getContext('2d');
      if (!ctx) return null;
      ctx.drawImage(img, 0, 0);
      return canvas.toDataURL('image/png');
    } catch {
      return null;
    }
  }
}

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
