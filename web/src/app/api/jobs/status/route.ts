import { NextResponse, type NextRequest } from 'next/server';
import { ObjectId } from 'mongodb';
import { getCurrentKey } from '@/lib/auth';
import { collections } from '@/lib/db';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  const current = await getCurrentKey();
  if (!current?.record) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const ids = (req.nextUrl.searchParams.get('ids') ?? '')
    .split(',')
    .filter(Boolean)
    .slice(0, 200);

  if (!ids.length) return NextResponse.json({ jobs: [] });

  let objectIds: ObjectId[];
  try {
    objectIds = ids.map((i) => new ObjectId(i));
  } catch {
    return NextResponse.json({ error: 'Bad id' }, { status: 400 });
  }

  const c = await collections();
  const keyId = new ObjectId(current.keyId);

  const jobs = await c.jobs
    .find({ _id: { $in: objectIds }, keyId })
    .project({ _id: 1, status: 1, error: 1, imageId: 1 })
    .toArray();

  // Pull image data URLs in one go
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

  return NextResponse.json({
    jobs: jobs.map((j) => ({
      id: j._id?.toString(),
      status: j.status,
      error: j.error ?? null,
      imageUrl: j.imageId ? imageMap.get(j.imageId.toString()) ?? null : null,
    })),
  });
}
