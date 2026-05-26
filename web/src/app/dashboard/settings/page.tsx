import { Crown, Calendar, Hash, BarChart3 } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { getCurrentKey, rolloverDaily } from '@/lib/auth';
import { formatDate } from '@/lib/utils';

export default async function SettingsPage() {
  const current = await getCurrentKey();
  if (!current?.record) return null;
  const record = await rolloverDaily(current.record);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="mt-1 text-muted-foreground">
          Your access key details and usage stats.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Crown className="h-5 w-5 text-primary" />
            Plan
          </CardTitle>
          <CardDescription>{current.planName}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6 sm:grid-cols-2">
          <Detail
            icon={Hash}
            label="Access key"
            value={
              <span className="font-mono text-xs tracking-wider">{current.key}</span>
            }
          />
          <Detail
            icon={Calendar}
            label="Created"
            value={formatDate(record.createdAt)}
          />
          <Detail
            icon={Calendar}
            label="Expires"
            value={record.expiresAt ? formatDate(record.expiresAt) : 'No expiry'}
          />
          <Detail
            icon={BarChart3}
            label="Status"
            value={
              <Badge variant={record.revoked ? 'destructive' : 'success'}>
                {record.revoked ? 'Revoked' : 'Active'}
              </Badge>
            }
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Usage</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-6 sm:grid-cols-3">
          <Stat label="Total images" value={record.totalUsed} />
          <Stat label="Today" value={record.dailyUsed} />
          <Stat
            label="Last used"
            value={record.lastUsedAt ? formatDate(record.lastUsedAt) : '—'}
          />
        </CardContent>
      </Card>
    </div>
  );
}

function Detail({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <p className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground">
        <Icon className="h-3 w-3" />
        {label}
      </p>
      <div>{value}</div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}
