import { type NextRequest } from 'next/server';
import { ObjectId } from 'mongodb';
import { collections } from '@/lib/db';
import { getAdminKeyId, requireAdmin } from '@/lib/admin-auth';
import { preflight, jsonWithCors, corsHeaders } from '@/lib/worker-auth';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function OPTIONS(req: NextRequest) {
  return preflight(req) ?? new Response(null, { headers: corsHeaders(req.headers.get('origin')) });
}

export async function GET(req: NextRequest) {
  const authError = requireAdmin(req);
  if (authError) return authError;

  const ids = (req.nextUrl.searchParams.get('ids') ?? '')
    .split(',')
    .filter(Boolean)
    .slice(0, 500);

  const c = await collections();
  const keyId = await getAdminKeyId();

  let cursor;
  if (ids.length) {
    let objectIds: ObjectId[];
    try {
      objectIds = ids.map((i) => new ObjectId(i));
    } catch {
      return jsonWithCors(req, { error: 'Bad id' }, { status: 400 });
    }
    cursor = c.jobs.find({ _id: { $in: objectIds }, keyId });
  } else {
    // No ids → return latest 50 admin jobs
    cursor = c.jobs.find({ keyId }).sort({ createdAt: -1 }).limit(50);
  }

  const jobs = await cursor.toArray();

  // Resolve image data URLs
  const imageIds = jobs
    .map((j) => j.imageId)
    .filter((id): id is ObjectId => !!id);
  const images = imageIds.length
    ? await c.images
        .find({ _id: { $in: imageIds } })
        .project({ _id: 1, dataUrl: 1 })
        .toArray()
    : [];
  const imageMap = new Map(images.map((i) => [i._id?.toString(), i.dataUrl]));

  return jsonWithCors(req, {
    jobs: jobs.map((j) => ({
      id: j._id?.toString(),
      prompt: j.prompt,
      status: j.status,
      error: j.error ?? null,
      imageUrl: j.imageId ? imageMap.get(j.imageId.toString()) ?? null : null,
      createdAt: j.createdAt.toISOString(),
    })),
  });
}
