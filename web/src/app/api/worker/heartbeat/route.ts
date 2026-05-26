import { type NextRequest } from 'next/server';
import { z } from 'zod';
import { collections } from '@/lib/db';
import {
  preflight,
  requireWorker,
  workerId,
  jsonWithCors,
  corsHeaders,
} from '@/lib/worker-auth';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function OPTIONS(req: NextRequest) {
  return preflight(req) ?? new Response(null, { headers: corsHeaders(req.headers.get('origin')) });
}

const Schema = z.object({
  label: z.string().max(100).optional(),
  version: z.string().max(20).optional(),
  accountsTotal: z.number().int().min(0).default(0),
  accountsActive: z.number().int().min(0).default(0),
  jobsToday: z.number().int().min(0).default(0),
});

export async function POST(req: NextRequest) {
  const auth = requireWorker(req);
  if (auth) return auth;

  const id = workerId(req);
  let body: z.infer<typeof Schema>;
  try {
    body = Schema.parse(await req.json());
  } catch {
    return jsonWithCors(req, { error: 'Invalid' }, { status: 400 });
  }

  const c = await collections();
  await c.heartbeats.updateOne(
    { workerId: id },
    {
      $set: {
        workerId: id,
        label: body.label,
        version: body.version,
        accountsTotal: body.accountsTotal,
        accountsActive: body.accountsActive,
        jobsToday: body.jobsToday,
        lastSeen: new Date(),
      },
    },
    { upsert: true }
  );
  return jsonWithCors(req, { ok: true });
}
