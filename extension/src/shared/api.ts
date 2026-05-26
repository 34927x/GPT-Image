/**
 * Chrome MV3 only. We re-export `chrome` as `api` so we can swap implementations
 * later without touching call sites.
 */
export const api = chrome;
