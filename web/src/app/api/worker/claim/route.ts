import { type NextRequest } from 'next/server';
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

/**
 * Worker pulls a single pending job atomically.
 * findOneAndUpdate ensures two workers can't grab the same job.
 */
export async function POST(req: NextRequest) {
  const auth = requireWorker(req);
  if (auth) return auth;
  const id = workerId(req);

  const c = await collections();
  const now = new Date();

  const job = await c.jobs.findOneAndUpdate(
    { status: 'pending' },
    {
      $set: {
        status: 'processing',
        workerId: id,
        startedAt: now,
      },
      $inc: { attempts: 1 },
    },
    {
      sort: { createdAt: 1 },
      returnDocument: 'after',
    }
  );

  if (!job) return jsonWithCors(req, { job: null });

  return jsonWithCors(req, {
    job: {
      id: job._id?.toString(),
      prompt: job.prompt,
      imageSize: job.imageSize,
      attempts: job.attempts,
    },
  });
}
