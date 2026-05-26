import {
  KeyRound,
  Users,
  Image as ImageIcon,
  Activity,
  Cpu,
  AlertCircle,
} from 'lucide-react';
import { collections, ensureIndexes } from '@/lib/db';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { formatRelative } from '@/lib/utils';

export default async function AdminOverview() {
  await ensureIndexes();
  const c = await collections();
  const now = new Date();

  const [
    totalKeys,
    activeKeys,
    revokedKeys,
    totalImages,
    pendingJobs,
    processingJobs,
    failedJobs,
    workers,
  ] = await Promise.all([
    c.keys.countDocuments({}),
    c.keys.countDocuments({
      revoked: false,
      $or: [{ expiresAt: null }, { expiresAt: { $gt: now } }],
    }),
    c.keys.countDocuments({ revoked: true }),
    c.images.countDocuments({}),
    c.jobs.countDocuments({ status: 'pending' }),
    c.jobs.countDocuments({ status: 'processing' }),
    c.jobs.countDocuments({ status: 'failed' }),
    c.heartbeats.find({}).sort({ lastSeen: -1 }).limit(5).toArray(),
  ]);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Admin overview</h1>
        <p className="mt-1 text-muted-foreground">
          Live metrics across the entire Bulk-GPT system.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={KeyRound}
          label="Active keys"
          value={activeKeys}
          sub={`${totalKeys} total · ${revokedKeys} revoked`}
          accent="from-primary/20 to-primary/0"
        />
        <StatCard
          icon={ImageIcon}
          label="Images generated"
          value={totalImages}
          sub="across all customers"
          accent="from-accent/20 to-accent/0"
        />
        <StatCard
          icon={Activity}
          label="In flight"
          value={pendingJobs + processingJobs}
          sub={`${pendingJobs} pending · ${processingJobs} processing`}
          accent="from-amber-500/20 to-amber-500/0"
        />
        <StatCard
          icon={AlertCircle}
          label="Failed jobs"
          value={failedJobs}
          sub="need investigation"
          accent="from-destructive/20 to-destructive/0"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Cpu className="h-5 w-5 text-accent" />
            Workers
          </CardTitle>
          <CardDescription>Connected extension workers</CardDescription>
        </CardHeader>
        <CardContent>
          {workers.length === 0 ? (
            <p className="rounded-lg border border-dashed border-border/60 py-12 text-center text-sm text-muted-foreground">
              No workers connected yet. Open the extension and start Worker Mode.
            </p>
          ) : (
            <div className="space-y-2">
              {workers.map((w) => {
                const isOnline = Date.now() - new Date(w.lastSeen).getTime() < 30_000;
                return (
                  <div
                    key={w.workerId}
                    className="flex items-center justify-between rounded-lg border border-border/60 bg-card/40 p-3"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={
                          'h-2 w-2 rounded-full ' +
                          (isOnline ? 'bg-emerald-400 animate-pulse' : 'bg-muted-foreground')
                        }
                      />
                      <div>
                        <p className="font-medium">
                          {w.label ?? w.workerId.slice(0, 12)}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {formatRelative(w.lastSeen)} · {w.accountsActive}/
                          {w.accountsTotal} accounts active
                        </p>
                      </div>
                    </div>
                    <Badge variant={isOnline ? 'success' : 'outline'}>
                      {isOnline ? 'Online' : 'Offline'}
                    </Badge>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  accent,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number;
  sub?: string;
  accent: string;
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
        <p className="text-3xl font-semibold tabular-nums">{value}</p>
        {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  );
}
