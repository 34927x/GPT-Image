import { storage, type Account } from '@/shared/storage';

/**
 * Pick the next usable account: oldest-used first, skipping rate-limited ones.
 * Returns null if all accounts are currently rate-limited or there are none.
 */
export async function pickNextAccount(): Promise<Account | null> {
  const accounts = await storage.getAccounts();
  if (!accounts.length) return null;
  const now = Date.now();
  const usable = accounts
    .filter((a) => !(a.rateLimitedUntil && a.rateLimitedUntil > now))
    .sort((x, y) => (x.lastUsedAt ?? 0) - (y.lastUsedAt ?? 0));
  return usable[0] ?? null;
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
  // Default cooldown: 1 hour if server didn't tell us when limits reset
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

/**
 * After a successful run, refresh the saved cookies for an account with the
 * latest values from the incognito session. Keeps tokens current.
 */
export async function updateAccountCookies(
  id: string,
  cookies: Account['cookies']
): Promise<void> {
  if (!cookies.length) return;
  const accounts = await storage.getAccounts();
  const a = accounts.find((x) => x.id === id);
  if (!a) return;
  a.cookies = cookies;
  a.capturedAt = Date.now();
  await storage.setAccounts(accounts);
}

export async function activeAccountsCount(): Promise<number> {
  const accounts = await storage.getAccounts();
  const now = Date.now();
  return accounts.filter((a) => !(a.rateLimitedUntil && a.rateLimitedUntil > now))
    .length;
}
