import { ObjectId } from 'mongodb';
import Link from 'next/link';
import { Wand2, ImageIcon } from 'lucide-react';
import { getCurrentKey } from '@/lib/auth';
import { collections } from '@/lib/db';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { GalleryGrid } from './gallery-grid';

const PAGE_SIZE = 60;

export default async function GalleryPage({
  searchParams,
}: {
  searchParams: Promise<{ p?: string }>;
}) {
  const current = await getCurrentKey();
  if (!current?.record) return null;

  const sp = await searchParams;
  const page = Math.max(1, Number(sp.p ?? 1));
  const c = await collections();
  const keyId = new ObjectId(current.keyId);

  const [images, total] = await Promise.all([
    c.images
      .find({ keyId })
      .sort({ createdAt: -1 })
      .skip((page - 1) * PAGE_SIZE)
      .limit(PAGE_SIZE)
      .toArray(),
    c.images.countDocuments({ keyId }),
  ]);

  const items = images.map((i) => ({
    id: i._id!.toString(),
    url: i.url,
    prompt: i.prompt,
    createdAt: i.createdAt.toISOString(),
  }));

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold">Gallery</h1>
          <p className="mt-1 text-muted-foreground">
            {total} image{total !== 1 ? 's' : ''} generated
          </p>
        </div>
        <Button asChild variant="gradient">
          <Link href="/dashboard/generate">
            <Wand2 className="h-4 w-4" />
            Generate more
          </Link>
        </Button>
      </div>

      {items.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-20 text-center">
            <div className="rounded-full bg-primary/10 p-4">
              <ImageIcon className="h-6 w-6 text-primary" />
            </div>
            <div>
              <p className="font-medium">No images yet</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Head to the generator to create your first batch.
              </p>
            </div>
            <Button asChild variant="gradient">
              <Link href="/dashboard/generate">
                <Wand2 className="h-4 w-4" />
                Start generating
              </Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <GalleryGrid items={items} />
          <Pagination page={page} total={total} pageSize={PAGE_SIZE} />
        </>
      )}
    </div>
  );
}

function Pagination({
  page,
  total,
  pageSize,
}: {
  page: number;
  total: number;
  pageSize: number;
}) {
  const pages = Math.ceil(total / pageSize);
  if (pages <= 1) return null;
  return (
    <div className="flex items-center justify-center gap-3 pt-4">
      <Button asChild variant="outline" size="sm" disabled={page <= 1}>
        <Link href={`?p=${page - 1}`}>Previous</Link>
      </Button>
      <span className="text-sm text-muted-foreground">
        Page {page} of {pages}
      </span>
      <Button asChild variant="outline" size="sm" disabled={page >= pages}>
        <Link href={`?p=${page + 1}`}>Next</Link>
      </Button>
    </div>
  );
}
