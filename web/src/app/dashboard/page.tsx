import Link from 'next/link';
import {
  Wand2,
  Image as ImageIcon,
  Activity,
  Sparkles,
  Calendar,
  Zap,
} from 'lucide-react';
import { ObjectId } from 'mongodb';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { getCurrentKey, rolloverDaily } from '@/lib/auth';
import { collections } from '@/lib/db';
import { formatDate, formatRelative } from '@/lib/utils';

export default async function DashboardOverview() {
  const current = await getCurrentKey();
  if (!current?.record) return null;
  const record = await rolloverDaily(current.record);

  const c = await collections();
  const keyId = new ObjectId(current.keyId);
  const [pending, processing, totalImages, recentImages] = await Promise.all([
    c.jobs.countDocuments({ keyId, status: 'pending' }),
    c.jobs.countDocuments({ keyId, status: 'processing' }),
    c.images.countDocuments({ keyId }),
    c.images.find({ keyId }).sort({ createdAt: -1 }).limit(6).toArray(),
  ]);

  // Quota math
  const dailyLimit = 0; // TODO: read from plans collection
  const dailyPct =
    dailyLimit > 0 ? Math.min(100, (record.dailyUsed / dailyLimit) * 100) : 0;

  const expiry = record.expiresAt ? formatDate(record.expiresAt) : 'No expiry';

  return (
    <div className="space-y-8">
      {/* HERO */}
      <section className="relative overflow-hidden rounded-2xl border border-border/60 bg-gradient-to-br from-primary/10 via-card/40 to-accent/5 p-8 backdrop-blur-xl">
        <div className="relative z-10 flex flex-col justify-between gap-6 sm:flex-row sm:items-center">
          <div>
            <p className="text-sm text-muted-foreground">Welcome back</p>
            <h1 className="mt-1 text-3xl font-bold sm:text-4xl">
              Let&apos;s make something <span className="gradient-text">amazing</span>.
            </h1>
            <p className="mt-2 text-muted-foreground">
              {pending + processing > 0
                ? `${pending + processing} job${
                    pending + processing > 1 ? 's' : ''
                  } in flight right now.`
                : 'Paste a stack of prompts and let Bulk-GPT do the rest.'}
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button asChild size="lg" variant="gradient">
              <Link href="/dashboard/generate">
                <Wand2 className="h-4 w-4" />
                Generate
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href="/dashboard/gallery">
                <ImageIcon className="h-4 w-4" />
                Gallery
              </Link>
            </Button>
          </div>
        </div>
        <div className="pointer-events-none absolute -right-20 -top-20 h-72 w-72 rounded-full bg-primary/30 blur-[120px]" />
        <div className="pointer-events-none absolute -bottom-20 -left-20 h-64 w-64 rounded-full bg-accent/20 blur-[120px]" />
      </section>

      {/* STATS */}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={ImageIcon}
          label="Total images"
          value={totalImages}
          accent="from-primary/20 to-primary/0"
        />
        <StatCard
          icon={Activity}
          label="In flight"
          value={pending + processing}
          accent="from-accent/20 to-accent/0"
        />
        <StatCard
          icon={Zap}
          label="Today"
          value={record.dailyUsed}
          accent="from-emerald-500/20 to-emerald-500/0"
          extra={
            dailyLimit > 0 && (
              <div className="mt-3">
                <Progress value={dailyPct} className="h-1" />
                <p className="mt-1 text-[10px] text-muted-foreground">
                  {record.dailyUsed} / {dailyLimit}
                </p>
              </div>
            )
          }
        />
        <StatCard
          icon={Calendar}
          label="Expires"
          value={expiry}
          accent="from-amber-500/20 to-amber-500/0"
          isString
        />
      </section>

      {/* RECENT */}
      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold">Recent images</h2>
          {totalImages > 0 && (
            <Button asChild variant="ghost" size="sm">
              <Link href="/dashboard/gallery">View all →</Link>
            </Button>
          )}
        </div>

        {recentImages.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center gap-4 py-16 text-center">
              <div className="rounded-full bg-primary/10 p-4">
                <Sparkles className="h-6 w-6 text-primary" />
              </div>
              <div>
                <p className="font-medium">No images yet</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Your generated images will show up here.
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
          <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
            {recentImages.map((img) => (
              <Link
                key={img._id?.toString()}
                href="/dashboard/gallery"
                className="group relative aspect-square overflow-hidden rounded-lg border border-border/60 bg-card/40"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={img.dataUrl}
                  alt={img.prompt}
                  className="h-full w-full object-cover transition-transform group-hover:scale-105"
                  loading="lazy"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 transition-opacity group-hover:opacity-100">
                  <div className="absolute bottom-0 p-2 text-xs text-white line-clamp-2">
                    {img.prompt}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  accent,
  isString,
  extra,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number | string;
  accent: string;
  isString?: boolean;
  extra?: React.ReactNode;
}) {
  return (
    <Card className="relative overflow-hidden">
      <div
        className={`pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full bg-gradient-to-br ${accent} blur-2xl`}
      />
      <CardHeader className="pb-2">
        <CardDescription className="flex items-center gap-2">
          <Icon className="h-4 w-4" />
          {label}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p
          className={`font-semibold tabular-nums ${
            isString ? 'text-base' : 'text-3xl'
          }`}
        >
          {value}
        </p>
        {extra}
      </CardContent>
    </Card>
  );
}
