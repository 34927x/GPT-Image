import Link from 'next/link';
import { ImageIcon } from 'lucide-react';
import { collections } from '@/lib/db';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { formatRelative } from '@/lib/utils';

const PAGE_SIZE = 60;

export const dynamic = 'force-dynamic';

export default async function AdminGallery({
  searchParams,
}: {
  searchParams: Promise<{ p?: string }>;
}) {
  const sp = await searchParams;
  const page = Math.max(1, Number(sp.p ?? 1));
  const c = await collections();

  const [images, total] = await Promise.all([
    c.images
      .find({})
      .sort({ createdAt: -1 })
      .skip((page - 1) * PAGE_SIZE)
      .limit(PAGE_SIZE)
      .toArray(),
    c.images.countDocuments({}),
  ]);

  // Resolve owners (key labels) — single roundtrip
  const keyIds = Array.from(new Set(images.map((i) => i.keyId)));
  const keyDocs = keyIds.length
    ? await c.keys
        .find({ _id: { $in: keyIds } })
        .project({ _id: 1, key: 1, planName: 1 })
        .toArray()
    : [];
  const keyMap = new Map(
    keyDocs.map((k) => [k._id?.toString(), { key: k.key, planName: k.planName }])
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">All images</h1>
        <p className="mt-1 text-muted-foreground">
          {total} image{total !== 1 ? 's' : ''} across all customers
        </p>
      </div>

      {images.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-20 text-center">
            <div className="rounded-full bg-primary/10 p-4">
              <ImageIcon className="h-6 w-6 text-primary" />
            </div>
            <p className="font-medium">No images yet</p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
            {images.map((img) => {
              const owner = keyMap.get(img.keyId.toString());
              return (
                <a
                  key={img._id?.toString()}
                  href={img.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group relative aspect-square overflow-hidden rounded-lg border border-border/60 bg-card/40"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={img.url}
                    alt={img.prompt}
                    loading="lazy"
                    className="h-full w-full object-cover transition-transform group-hover:scale-105"
                  />
                  <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/85 via-black/0 to-transparent opacity-0 transition-opacity group-hover:opacity-100">
                    <div className="absolute bottom-0 w-full p-2 text-left">
                      <p className="line-clamp-2 text-[11px] font-medium text-white">
                        {img.prompt}
                      </p>
                      <div className="mt-1 flex items-center justify-between">
                        <Badge variant="outline" className="text-[9px]">
                          {owner?.planName ?? '?'}
                        </Badge>
                        <span className="text-[9px] text-white/70">
                          {formatRelative(img.createdAt)}
                        </span>
                      </div>
                    </div>
                  </div>
                </a>
              );
            })}
          </div>

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
