import { type NextRequest } from 'next/server';
import { ObjectId } from 'mongodb';
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

const Schema = z.discriminatedUnion('outcome', [
  z.object({
    outcome: z.literal('success'),
    jobId: z.string().min(1),
    imageDataUrl: z.string().startsWith('data:image/'),
    account: z.string().max(80).optional(),
  }),
  z.object({
    outcome: z.literal('failure'),
    jobId: z.string().min(1),
    error: z.string().max(500),
  }),
]);

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

  let jobObjectId: ObjectId;
  try {
    jobObjectId = new ObjectId(body.jobId);
  } catch {
    return jsonWithCors(req, { error: 'Bad jobId' }, { status: 400 });
  }

  const c = await collections();
  const job = await c.jobs.findOne({ _id: jobObjectId });
  if (!job) return jsonWithCors(req, { error: 'Job not found' }, { status: 404 });

  const now = new Date();

  if (body.outcome === 'failure') {
    await c.jobs.updateOne(
      { _id: jobObjectId },
      {
        $set: {
          status: 'failed',
          error: body.error.slice(0, 500),
          finishedAt: now,
          workerId: id,
        },
      }
    );
    return jsonWithCors(req, { ok: true });
  }

  // SUCCESS — store data URL inline (TTL auto-deletes after 24h)
  const imageDoc = await c.images.insertOne({
    jobId: jobObjectId,
    keyId: job.keyId,
    prompt: job.prompt,
    dataUrl: body.imageDataUrl,
    account: body.account,
    createdAt: now,
  });

  await c.jobs.updateOne(
    { _id: jobObjectId },
    {
      $set: {
        status: 'done',
        imageId: imageDoc.insertedId,
        finishedAt: now,
        account: body.account ?? null,
        workerId: id,
      },
    }
  );

  await c.keys.updateOne(
    { _id: job.keyId },
    {
      $inc: { totalUsed: 1, dailyUsed: 1 },
      $set: { lastUsedAt: now },
    }
  );

  return jsonWithCors(req, { ok: true, imageId: imageDoc.insertedId.toString() });
}
