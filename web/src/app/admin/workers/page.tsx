import { Cpu } from 'lucide-react';
import { collections } from '@/lib/db';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { formatRelative } from '@/lib/utils';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function WorkersPage() {
  const c = await collections();
  const workers = await c.heartbeats.find().sort({ lastSeen: -1 }).toArray();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Workers</h1>
        <p className="mt-1 text-muted-foreground">
          Bulk-GPT extensions running in worker mode.
        </p>
      </div>

      {workers.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-20 text-center">
            <div className="rounded-full bg-primary/10 p-4">
              <Cpu className="h-6 w-6 text-primary" />
            </div>
            <div>
              <p className="font-medium">No workers connected</p>
              <p className="mt-1 max-w-md text-sm text-muted-foreground">
                Open the Bulk-GPT extension on your machine, paste your worker token in
                Settings, then enable Worker Mode. It&apos;ll appear here within a few
                seconds.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {workers.map((w) => {
            const isOnline = Date.now() - new Date(w.lastSeen).getTime() < 30_000;
            return (
              <Card key={w.workerId}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">
                      {w.label ?? w.workerId.slice(0, 12)}
                    </CardTitle>
                    <Badge variant={isOnline ? 'success' : 'outline'}>
                      <span
                        className={
                          'mr-1 h-1.5 w-1.5 rounded-full ' +
                          (isOnline ? 'bg-emerald-400 animate-pulse' : 'bg-muted-foreground')
                        }
                      />
                      {isOnline ? 'Online' : 'Offline'}
                    </Badge>
                  </div>
                  <CardDescription className="font-mono text-xs">
                    {w.workerId}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <Row label="Last seen" value={formatRelative(w.lastSeen)} />
                  <Row
                    label="Accounts"
                    value={`${w.accountsActive}/${w.accountsTotal}`}
                  />
                  <Row label="Jobs today" value={w.jobsToday.toString()} />
                  <Row label="Version" value={w.version ?? '—'} />
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
