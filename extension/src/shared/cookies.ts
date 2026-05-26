import { api } from './api';
import type { Cookie } from './storage';

const DOMAINS = ['chatgpt.com', '.openai.com'];

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
  return out;
}

export function hasSessionCookie(cookies: Cookie[]): boolean {
  return cookies.some((c) => /session|token|auth/i.test(c.name));
}

export async function clearAllCookies(): Promise<void> {
  for (const domain of DOMAINS) {
    try {
      const cookies = await api.cookies.getAll({ domain });
      await Promise.all(
        cookies.map((c) => {
          const d = c.domain.startsWith('.') ? c.domain.slice(1) : c.domain;
          return api.cookies
            .remove({ url: `https://${d}${c.path}`, name: c.name })
            .catch(() => {});
        })
      );
    } catch {
      /* ignore */
    }
  }
}

export async function restoreCookies(cookies: Cookie[]): Promise<void> {
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
      });
    } catch {
      /* skip rejected cookies */
    }
  }
}
