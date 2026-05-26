import { collections, ensureIndexes } from '@/lib/db';
import { Card, CardContent } from '@/components/ui/card';
import { KeysClient } from './keys-client';

export default async function AdminKeysPage() {
  await ensureIndexes();
  const c = await collections();
  const [keys, plans] = await Promise.all([
    c.keys.find().sort({ createdAt: -1 }).limit(500).toArray(),
    c.plans.find().sort({ name: 1 }).toArray(),
  ]);

  const serializedKeys = keys.map((k) => ({
    id: k._id!.toString(),
    key: k.key,
    planName: k.planName,
    note: k.note ?? '',
    revoked: k.revoked,
    createdAt: k.createdAt.toISOString(),
    expiresAt: k.expiresAt?.toISOString() ?? null,
    totalUsed: k.totalUsed,
    dailyUsed: k.dailyUsed,
    lastUsedAt: k.lastUsedAt?.toISOString() ?? null,
  }));
  const planNames = plans.map((p) => p.name);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Access keys</h1>
        <p className="mt-1 text-muted-foreground">
          Generate, revoke, and audit customer access keys.
        </p>
      </div>
      <Card>
        <CardContent className="p-0">
          <KeysClient initialKeys={serializedKeys} planNames={planNames} />
        </CardContent>
      </Card>
    </div>
  );
}
