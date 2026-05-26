import { collections, ensureIndexes } from '@/lib/db';
import { Card, CardContent } from '@/components/ui/card';
import { PlansClient } from './plans-client';

export default async function AdminPlansPage() {
  await ensureIndexes();
  const c = await collections();
  const plans = await c.plans.find().sort({ name: 1 }).toArray();

  const items = plans.map((p) => ({
    id: p._id!.toString(),
    name: p.name,
    dailyImageLimit: p.dailyImageLimit,
    totalImageLimit: p.totalImageLimit,
    validityDays: p.validityDays,
    description: p.description ?? '',
    createdAt: p.createdAt.toISOString(),
  }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Plans</h1>
        <p className="mt-1 text-muted-foreground">
          Define what an access key gives the customer.
        </p>
      </div>
      <Card>
        <CardContent className="p-6">
          <PlansClient initialPlans={items} />
        </CardContent>
      </Card>
    </div>
  );
}
