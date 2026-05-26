import { storage, type Account } from '@/shared/storage';
import { clearAllCookies, restoreCookies } from '@/shared/cookies';

let switching = false;

export async function getActiveAccount(): Promise<Account | null> {
  const accounts = await storage.getAccounts();
  if (!accounts.length) return null;
  const idx = await storage.getActiveIndex();
  return accounts[idx] ?? accounts[0];
}

export async function pickNextAccount(): Promise<Account | null> {
  const accounts = await storage.getAccounts();
  if (!accounts.length) return null;
  const now = Date.now();
  // Sort by oldest lastUsedAt first, ignoring rate-limited
  const usable = accounts
    .map((a, i) => ({ a, i }))
    .filter(({ a }) => !(a.rateLimitedUntil && a.rateLimitedUntil > now))
    .sort((x, y) => (x.a.lastUsedAt ?? 0) - (y.a.lastUsedAt ?? 0));
  if (!usable.length) return null;
  return usable[0].a;
}

export async function switchToAccount(id: string): Promise<boolean> {
  if (switching) return false;
  switching = true;
  try {
    const accounts = await storage.getAccounts();
    const idx = accounts.findIndex((a) => a.id === id);
    if (idx < 0) return false;
    await clearAllCookies();
    await restoreCookies(accounts[idx].cookies);
    await storage.setActiveIndex(idx);
    accounts[idx].lastUsedAt = Date.now();
    await storage.setAccounts(accounts);
    return true;
  } finally {
    switching = false;
  }
}

export async function markAccountSuccess(id: string): Promise<void> {
  const accounts = await storage.getAccounts();
  const a = accounts.find((x) => x.id === id);
  if (!a) return;
  a.errorCount = 0;
  a.lastUsedAt = Date.now();
  await storage.setAccounts(accounts);
}

export async function markAccountRateLimited(
  id: string,
  resetAt?: number
): Promise<void> {
  const accounts = await storage.getAccounts();
  const a = accounts.find((x) => x.id === id);
  if (!a) return;
  // Default: 1 hour cooldown if server didn't tell us
  a.rateLimitedUntil = resetAt ?? Date.now() + 60 * 60 * 1000;
  await storage.setAccounts(accounts);
}

export async function markAccountError(id: string): Promise<void> {
  const accounts = await storage.getAccounts();
  const a = accounts.find((x) => x.id === id);
  if (!a) return;
  a.errorCount += 1;
  await storage.setAccounts(accounts);
}

export async function activeAccountsCount(): Promise<number> {
  const accounts = await storage.getAccounts();
  const now = Date.now();
  return accounts.filter((a) => !(a.rateLimitedUntil && a.rateLimitedUntil > now))
    .length;
}
