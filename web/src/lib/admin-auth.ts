import { type NextRequest, NextResponse } from 'next/server';
import { ObjectId } from 'mongodb';
import { collections, ensureIndexes } from './db';
import { env } from './env';

const ADMIN_LABEL = '__admin__';

/**
 * Verify the admin master key from a request header.
 * Returns null on success, otherwise an error response.
 */
export function requireAdmin(req: NextRequest): NextResponse | null {
  const key =
    req.headers.get('x-admin-key') ??
    req.headers.get('authorization')?.replace(/^Bearer\s+/i, '') ??
    '';
  if (!key || key.trim().toUpperCase() !== env.ADMIN_MASTER_KEY.toUpperCase()) {
    return NextResponse.json({ error: 'Invalid admin key' }, { status: 401 });
  }
  return null;
}

/**
 * Returns the synthetic admin "key" record id used to associate admin-generated
 * jobs / images with a single owner. Created on first call.
 */
export async function getAdminKeyId(): Promise<ObjectId> {
  await ensureIndexes();
  const c = await collections();
  let doc = await c.keys.findOne({ key: ADMIN_LABEL });
  if (doc) return doc._id!;
  const now = new Date();
  const result = await c.keys.insertOne({
    key: ADMIN_LABEL,
    planName: 'Admin',
    note: 'Admin pseudo-key (for extension generate tab)',
    createdAt: now,
    expiresAt: null,
    revoked: false,
    totalUsed: 0,
    dailyUsed: 0,
    dailyResetAt: now,
    lastUsedAt: null,
    isAdmin: true,
  });
  return result.insertedId;
}
