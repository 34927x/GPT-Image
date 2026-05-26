import { NextResponse, type NextRequest } from 'next/server';
import { ObjectId } from 'mongodb';
import { z } from 'zod';
import { getCurrentKey, rolloverDaily } from '@/lib/auth';
import { collections, ensureIndexes } from '@/lib/db';
import type { Job } from '@/lib/types';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const Schema = z.object({
  prompts: z.array(z.string().trim().min(1).max(4000)).min(1).max(200),
  size: z.enum(['1:1', '16:9', '9:16', '4:3']).default('1:1'),
});

export async function POST(req: NextRequest) {
  const current = await getCurrentKey();
  if (!current) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  if (current.isAdmin || !current.record) {
    return NextResponse.json({ error: 'Use a customer key to generate' }, { status: 403 });
  }

  let body: z.infer<typeof Schema>;
  try {
    body = Schema.parse(await req.json());
  } catch {
    return NextResponse.json({ error: 'Invalid request' }, { status: 400 });
  }

  await ensureIndexes();
  const record = await rolloverDaily(current.record);
  const c = await collections();
  const keyId = new ObjectId(current.keyId);
  const batchId = new ObjectId().toHexString();
  const now = new Date();

  const docs: Job[] = body.prompts.map((prompt) => ({
    keyId,
    prompt,
    imageSize: body.size,
    status: 'pending',
    createdAt: now,
    attempts: 0,
    batchId,
  }));

  const insert = await c.jobs.insertMany(docs);

  return NextResponse.json({
    success: true,
    batchId,
    jobs: body.prompts.map((prompt, i) => ({
      id: insert.insertedIds[i].toString(),
      prompt,
    })),
    quota: {
      dailyUsed: record.dailyUsed,
      totalUsed: record.totalUsed,
    },
  });
}
