'use client';

import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { Plus, Trash2, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { upsertPlanAction, deletePlanAction } from './actions';

interface Plan {
  id: string;
  name: string;
  dailyImageLimit: number;
  totalImageLimit: number;
  validityDays: number;
  description: string;
  createdAt: string;
}

export function PlansClient({ initialPlans }: { initialPlans: Plan[] }) {
  const router = useRouter();
  const [plans, setPlans] = useState(initialPlans);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Plan | null>(null);
  const [pending, startTransition] = useTransition();

  const empty = {
    name: '',
    dailyImageLimit: 0,
    totalImageLimit: 0,
    validityDays: 30,
    description: '',
  };
  const [form, setForm] = useState(empty);

  function openNew() {
    setEditing(null);
    setForm(empty);
    setOpen(true);
  }

  function openEdit(p: Plan) {
    setEditing(p);
    setForm({
      name: p.name,
      dailyImageLimit: p.dailyImageLimit,
      totalImageLimit: p.totalImageLimit,
      validityDays: p.validityDays,
      description: p.description,
    });
    setOpen(true);
  }

  function save() {
    if (!form.name.trim()) {
      toast.error('Plan needs a name');
      return;
    }
    startTransition(async () => {
      const res = await upsertPlanAction(form);
      if (!res.success) {
        toast.error(res.error);
        return;
      }
      toast.success(editing ? 'Plan updated' : 'Plan created');
      setOpen(false);
      router.refresh();
    });
  }

  function remove(id: string) {
    if (!confirm('Delete this plan? Existing keys keep their settings.')) return;
    startTransition(async () => {
      const res = await deletePlanAction(id);
      if (!res.success) {
        toast.error(res.error);
        return;
      }
      setPlans((prev) => prev.filter((p) => p.id !== id));
      toast.success('Plan deleted');
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button variant="gradient" onClick={openNew}>
          <Plus className="h-4 w-4" />
          New plan
        </Button>
      </div>

      {plans.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border/60 py-16 text-center text-sm text-muted-foreground">
          Create your first plan to start issuing keys.
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {plans.map((p) => (
            <button
              key={p.id}
              onClick={() => openEdit(p)}
              className="group flex flex-col gap-3 rounded-xl border border-border/60 bg-card/50 p-5 text-left transition-all hover:border-primary/40 hover:bg-card/70"
            >
              <div className="flex items-start justify-between">
                <h3 className="font-semibold">{p.name}</h3>
                <span
                  role="button"
                  tabIndex={0}
                  onClick={(e) => {
                    e.stopPropagation();
                    remove(p.id);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.stopPropagation();
                      remove(p.id);
                    }
                  }}
                  className="cursor-pointer rounded p-1 opacity-0 transition-opacity hover:bg-destructive/10 group-hover:opacity-100"
                >
                  <Trash2 className="h-3.5 w-3.5 text-destructive" />
                </span>
              </div>

              {p.description && (
                <p className="text-sm text-muted-foreground line-clamp-2">{p.description}</p>
              )}

              <div className="flex flex-wrap gap-2 mt-auto">
                <Badge variant="outline">
                  {p.dailyImageLimit > 0 ? `${p.dailyImageLimit}/day` : 'Unlimited/day'}
                </Badge>
                <Badge variant="outline">
                  {p.totalImageLimit > 0
                    ? `${p.totalImageLimit} total`
                    : 'No total cap'}
                </Badge>
                <Badge variant="outline">
                  {p.validityDays > 0 ? `${p.validityDays} days` : 'No expiry'}
                </Badge>
              </div>
            </button>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? 'Edit plan' : 'New plan'}</DialogTitle>
            <DialogDescription>
              Use 0 to mean unlimited / no expiry.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Name</Label>
              <Input
                placeholder="Starter / Pro / Lifetime"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                disabled={!!editing}
              />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-2">
                <Label>Daily limit</Label>
                <Input
                  type="number"
                  min={0}
                  value={form.dailyImageLimit}
                  onChange={(e) =>
                    setForm({ ...form, dailyImageLimit: Number(e.target.value) || 0 })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Total cap</Label>
                <Input
                  type="number"
                  min={0}
                  value={form.totalImageLimit}
                  onChange={(e) =>
                    setForm({ ...form, totalImageLimit: Number(e.target.value) || 0 })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Validity (days)</Label>
                <Input
                  type="number"
                  min={0}
                  value={form.validityDays}
                  onChange={(e) =>
                    setForm({ ...form, validityDays: Number(e.target.value) || 0 })
                  }
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Internal description"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button variant="gradient" onClick={save} disabled={pending}>
              {pending && <Loader2 className="animate-spin" />}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
