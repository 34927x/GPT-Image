'use server';

import { ObjectId } from 'mongodb';
import { z } from 'zod';
import { getCurrentKey } from '@/lib/auth';
import { collections, ensureIndexes } from '@/lib/db';

async function requireAdmin() {
  const current = await getCurrentKey();
  if (!current?.isAdmin) throw new Error('Unauthorized');
}

const PlanSchema = z.object({
  name: z.string().trim().min(1).max(100),
  dailyImageLimit: z.number().int().min(0).max(100000).default(0),
  totalImageLimit: z.number().int().min(0).max(1000000).default(0),
  validityDays: z.number().int().min(0).max(3650).default(30),
  description: z.string().max(300).optional(),
});

export async function upsertPlanAction(
  input: z.infer<typeof PlanSchema>
): Promise<{ success: true } | { success: false; error: string }> {
  try {
    await requireAdmin();
    const data = PlanSchema.parse(input);
    await ensureIndexes();
    const c = await collections();
    await c.plans.updateOne(
      { name: data.name },
      {
        $set: {
          dailyImageLimit: data.dailyImageLimit,
          totalImageLimit: data.totalImageLimit,
          validityDays: data.validityDays,
          description: data.description,
        },
        $setOnInsert: { name: data.name, createdAt: new Date() },
      },
      { upsert: true }
    );
    return { success: true };
  } catch (e) {
    return { success: false, error: e instanceof Error ? e.message : 'Failed' };
  }
}

export async function deletePlanAction(
  id: string
): Promise<{ success: true } | { success: false; error: string }> {
  try {
    await requireAdmin();
    const c = await collections();
    await c.plans.deleteOne({ _id: new ObjectId(id) });
    return { success: true };
  } catch (e) {
    return { success: false, error: e instanceof Error ? e.message : 'Failed' };
  }
}
