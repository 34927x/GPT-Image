'use server';

import { ObjectId } from 'mongodb';
import { z } from 'zod';
import { getCurrentKey } from '@/lib/auth';
import { collections, ensureIndexes } from '@/lib/db';
import { generateKey } from '@/lib/utils';
import type { AccessKey } from '@/lib/types';

async function requireAdmin() {
  const current = await getCurrentKey();
  if (!current?.isAdmin) {
    throw new Error('Unauthorized');
  }
  return current;
}

const CreateSchema = z.object({
  planName: z.string().min(1).max(100),
  note: z.string().max(200).optional(),
  count: z.number().int().min(1).max(50),
});

interface CreatedKey {
  id: string;
  key: string;
  planName: string;
  note: string;
  revoked: boolean;
  createdAt: string;
  expiresAt: string | null;
  totalUsed: number;
  dailyUsed: number;
  lastUsedAt: string | null;
}

export async function createKeyAction(
  input: z.infer<typeof CreateSchema>
): Promise<{ success: true; created: CreatedKey[] } | { success: false; error: string }> {
  try {
    await requireAdmin();
    const data = CreateSchema.parse(input);

    await ensureIndexes();
    const c = await collections();
    const plan = await c.plans.findOne({ name: data.planName });
    if (!plan) return { success: false, error: 'Plan not found' };

    const now = new Date();
    const expiresAt = plan.validityDays > 0
      ? new Date(now.getTime() + plan.validityDays * 24 * 60 * 60 * 1000)
      : null;

    const docs: AccessKey[] = Array.from({ length: data.count }, () => ({
      key: generateKey(),
      planName: plan.name,
      note: data.note,
      createdAt: now,
      expiresAt,
      revoked: false,
      totalUsed: 0,
      dailyUsed: 0,
      dailyResetAt: now,
      lastUsedAt: null,
    }));

    const result = await c.keys.insertMany(docs);

    return {
      success: true,
      created: docs.map((d, i) => ({
        id: result.insertedIds[i].toString(),
        key: d.key,
        planName: d.planName,
        note: d.note ?? '',
        revoked: false,
        createdAt: d.createdAt.toISOString(),
        expiresAt: d.expiresAt?.toISOString() ?? null,
        totalUsed: 0,
        dailyUsed: 0,
        lastUsedAt: null,
      })),
    };
  } catch (e) {
    return { success: false, error: e instanceof Error ? e.message : 'Failed' };
  }
}

export async function toggleRevokeAction(
  id: string
): Promise<{ success: true } | { success: false; error: string }> {
  try {
    await requireAdmin();
    const c = await collections();
    const oid = new ObjectId(id);
    const doc = await c.keys.findOne({ _id: oid });
    if (!doc) return { success: false, error: 'Not found' };
    await c.keys.updateOne({ _id: oid }, { $set: { revoked: !doc.revoked } });
    return { success: true };
  } catch (e) {
    return { success: false, error: e instanceof Error ? e.message : 'Failed' };
  }
}

export async function updateNoteAction(
  id: string,
  note: string
): Promise<{ success: true } | { success: false; error: string }> {
  try {
    await requireAdmin();
    const c = await collections();
    await c.keys.updateOne({ _id: new ObjectId(id) }, { $set: { note: note.slice(0, 200) } });
    return { success: true };
  } catch (e) {
    return { success: false, error: e instanceof Error ? e.message : 'Failed' };
  }
}
