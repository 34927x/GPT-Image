import { ObjectId } from 'mongodb';
import { collections, ensureIndexes } from './db';
import { env } from './env';
import { getSession } from './session';
import type { AccessKey } from './types';

export class AuthError extends Error {
  constructor(public code: 'INVALID_KEY' | 'REVOKED' | 'EXPIRED' | 'NO_SESSION') {
    super(code);
  }
}

/**
 * Validate a key against the DB. The master admin key bypasses DB.
 */
export async function validateKey(key: string): Promise<{
  keyId: string;
  key: string;
  planName: string;
  isAdmin: boolean;
}> {
  const trimmed = key.trim().toUpperCase();
  if (!trimmed) throw new AuthError('INVALID_KEY');

  if (trimmed === env.ADMIN_MASTER_KEY.toUpperCase()) {
    return {
      keyId: 'admin',
      key: trimmed,
      planName: 'Admin',
      isAdmin: true,
    };
  }

  await ensureIndexes();
  const c = await collections();
  const doc = await c.keys.findOne({ key: trimmed });
  if (!doc) throw new AuthError('INVALID_KEY');
  if (doc.revoked) throw new AuthError('REVOKED');
  if (doc.expiresAt && doc.expiresAt.getTime() < Date.now()) {
    throw new AuthError('EXPIRED');
  }

  return {
    keyId: doc._id!.toString(),
    key: doc.key,
    planName: doc.planName,
    isAdmin: !!doc.isAdmin,
  };
}

/**
 * Read current session and resolve it to a key record (or admin).
 * Returns null if no/invalid session.
 */
export async function getCurrentKey(): Promise<{
  keyId: string;
  key: string;
  planName: string;
  isAdmin: boolean;
  record: AccessKey | null;
} | null> {
  const session = await getSession();
  if (!session.keyId || !session.key) return null;

  if (session.isAdmin) {
    return {
      keyId: 'admin',
      key: session.key,
      planName: 'Admin',
      isAdmin: true,
      record: null,
    };
  }

  await ensureIndexes();
  const c = await collections();
  let record: AccessKey | null = null;
  try {
    record = await c.keys.findOne({ _id: new ObjectId(session.keyId) });
  } catch {
    return null;
  }

  if (!record || record.revoked) return null;
  if (record.expiresAt && record.expiresAt.getTime() < Date.now()) return null;

  return {
    keyId: record._id!.toString(),
    key: record.key,
    planName: record.planName,
    isAdmin: false,
    record,
  };
}

/**
 * Reset the daily quota counter if the calendar day changed.
 */
export async function rolloverDaily(record: AccessKey): Promise<AccessKey> {
  const now = new Date();
  const last = record.dailyResetAt ? new Date(record.dailyResetAt) : null;
  if (!last || last.toDateString() !== now.toDateString()) {
    const c = await collections();
    await c.keys.updateOne(
      { _id: record._id },
      { $set: { dailyUsed: 0, dailyResetAt: now } }
    );
    return { ...record, dailyUsed: 0, dailyResetAt: now };
  }
  return record;
}
