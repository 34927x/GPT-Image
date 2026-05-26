import { type NextRequest } from 'next/server';
import { z } from 'zod';
import { collections, ensureIndexes } from '@/lib/db';
import { getAdminKeyId, requireAdmin } from '@/lib/admin-auth';
import {
  preflight,
  jsonWithCors,
  corsHeaders,
} from '@/lib/worker-auth';
import type { Job } from '@/lib/types';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const Schema = z.object({
  prompts: z.array(z.string().trim().min(1).max(4000)).min(1).max(500),
  size: z.enum(['1:1', '16:9', '9:16', '4:3']).default('1:1'),
});

export async function OPTIONS(req: NextRequest) {
  return preflight(req) ?? new Response(null, { headers: corsHeaders(req.headers.get('origin')) });
}

export async function POST(req: NextRequest) {
  const authError = requireAdmin(req);
  if (authError) return authError;

  let body: z.infer<typeof Schema>;
  try {
    body = Schema.parse(await req.json());
  } catch {
    return jsonWithCors(req, { error: 'Invalid request' }, { status: 400 });
  }

  await ensureIndexes();
  const c = await collections();
  const keyId = await getAdminKeyId();
  const now = new Date();
  const batchId = crypto.randomUUID();

  const docs: Job[] = body.prompts.map((prompt) => ({
    keyId,
    prompt,
    imageSize: body.size,
    status: 'pending',
    createdAt: now,
    attempts: 0,
    batchId,
  }));

  const result = await c.jobs.insertMany(docs);

  return jsonWithCors(req, {
    success: true,
    batchId,
    jobs: body.prompts.map((prompt, i) => ({
      id: result.insertedIds[i].toString(),
      prompt,
    })),
  });
}
