/**
 * Browser API shim — works in Chrome (chrome.*) and Firefox (browser.*).
 */
export const api: typeof chrome = (() => {
  if (typeof globalThis.browser !== 'undefined') return globalThis.browser as unknown as typeof chrome;
  return globalThis.chrome;
})();

export const isFirefox = typeof globalThis.browser !== 'undefined';
