'use server';

import { z } from 'zod';
import { AuthError, validateKey } from '@/lib/auth';
import { getSession } from '@/lib/session';

const KEY_SCHEMA = z.string().min(8).max(64);

export async function loginAction(
  rawKey: string
): Promise<{ success: true; redirect: string } | { success: false; error: string }> {
  const parsed = KEY_SCHEMA.safeParse(rawKey);
  if (!parsed.success) {
    return { success: false, error: 'Key looks too short.' };
  }

  try {
    const result = await validateKey(parsed.data);
    const session = await getSession();
    session.keyId = result.keyId;
    session.key = result.key;
    session.planName = result.planName;
    session.isAdmin = result.isAdmin;
    await session.save();
    return {
      success: true,
      redirect: result.isAdmin ? '/admin' : '/dashboard',
    };
  } catch (e) {
    if (e instanceof AuthError) {
      const map: Record<typeof e.code, string> = {
        INVALID_KEY: 'Invalid key. Check with your seller.',
        REVOKED: 'This key has been revoked.',
        EXPIRED: 'This key has expired.',
        NO_SESSION: 'Session error.',
      };
      return { success: false, error: map[e.code] };
    }
    return { success: false, error: 'Something went wrong. Try again.' };
  }
}

export async function logoutAction(): Promise<void> {
  const session = await getSession();
  session.destroy();
}
