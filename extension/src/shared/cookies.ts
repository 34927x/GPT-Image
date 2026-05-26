import { api } from './api';
import type { Cookie } from './storage';

/**
 * Domains that ChatGPT touches. We capture from all of them so refresh tokens
 * (which sometimes live on auth.openai.com) come along.
 */
const DOMAINS = ['chatgpt.com', '.openai.com', 'auth0.openai.com'];

/**
 * Capture cookies for the current (normal) browsing session.
 * Used when the user logs in normally and clicks "Capture session".
 */
export async function captureCurrentCookies(): Promise<Cookie[]> {
  const out: Cookie[] = [];
  for (const domain of DOMAINS) {
    try {
      const cookies = await api.cookies.getAll({ domain });
      for (const c of cookies) {
        out.push({
          name: c.name,
          value: c.value,
          domain: c.domain,
          path: c.path,
          secure: c.secure,
          httpOnly: c.httpOnly,
          sameSite: c.sameSite as Cookie['sameSite'],
          expirationDate: c.expirationDate,
        });
      }
    } catch {
      /* domain may not be accessible */
    }
  }
  // Deduplicate by (domain, name) — chatgpt.com and .openai.com can overlap
  const seen = new Set<string>();
  const dedup: Cookie[] = [];
  for (const c of out) {
    const k = `${c.domain}|${c.name}`;
    if (seen.has(k)) continue;
    seen.add(k);
    dedup.push(c);
  }
  return dedup;
}

export function hasSessionCookie(cookies: Cookie[]): boolean {
  return cookies.some((c) =>
    /session|token|auth|secure-next-auth/i.test(c.name)
  );
}

/**
 * Capture cookies from a specific incognito tab's cookie store.
 * Used after a worker run to refresh saved cookies in DB.
 *
 * `storeId` lets us read a specific incognito session's cookies.
 */
export async function captureFromStore(storeId: string): Promise<Cookie[]> {
  const out: Cookie[] = [];
  for (const domain of DOMAINS) {
    try {
      const cookies = await api.cookies.getAll({ domain, storeId });
      for (const c of cookies) {
        out.push({
          name: c.name,
          value: c.value,
          domain: c.domain,
          path: c.path,
          secure: c.secure,
          httpOnly: c.httpOnly,
          sameSite: c.sameSite as Cookie['sameSite'],
          expirationDate: c.expirationDate,
        });
      }
    } catch {
      /* skip */
    }
  }
  return out;
}

/**
 * Clear all chatgpt/openai cookies from a specific cookie store.
 */
export async function clearStore(storeId: string): Promise<void> {
  for (const domain of DOMAINS) {
    try {
      const cookies = await api.cookies.getAll({ domain, storeId });
      await Promise.all(
        cookies.map((c) => {
          const d = c.domain.startsWith('.') ? c.domain.slice(1) : c.domain;
          return api.cookies
            .remove({ url: `https://${d}${c.path}`, name: c.name, storeId })
            .catch(() => undefined);
        })
      );
    } catch {
      /* ignore */
    }
  }
}

/**
 * Inject a saved set of cookies into a specific cookie store (e.g. an
 * incognito session). The store must already exist; create it by opening
 * an incognito tab and reading its `cookieStoreId`.
 */
export async function injectIntoStore(
  cookies: Cookie[],
  storeId: string
): Promise<{ injected: number; failed: number }> {
  let injected = 0;
  let failed = 0;
  for (const c of cookies) {
    const d = c.domain.startsWith('.') ? c.domain.slice(1) : c.domain;
    try {
      await api.cookies.set({
        url: `https://${d}${c.path || '/'}`,
        name: c.name,
        value: c.value,
        domain: c.domain,
        path: c.path || '/',
        secure: c.secure,
        httpOnly: c.httpOnly,
        sameSite: c.sameSite,
        expirationDate: c.expirationDate,
        storeId,
      });
      injected++;
    } catch {
      failed++;
    }
  }
  return { injected, failed };
}
