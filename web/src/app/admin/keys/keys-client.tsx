'use client';

import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import {
  Plus,
  Copy,
  Ban,
  Check,
  ShieldOff,
  ShieldCheck,
  Search,
  Loader2,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { formatDate, formatRelative } from '@/lib/utils';
import {
  createKeyAction,
  toggleRevokeAction,
  updateNoteAction,
} from './actions';

interface KeyRow {
  id: string;
  key: string;
  planName: string;
  note: string;
  revoked: boolean;
  createdAt: string;
  expiresAt: string | null;
  totalUsed: number;
  dailyUsed: number;
  lastUsedAt: string | null;
}

export function KeysClient({
  initialKeys,
  planNames,
}: {
  initialKeys: KeyRow[];
  planNames: string[];
}) {
  const router = useRouter();
  const [keys, setKeys] = useState(initialKeys);
  const [filter, setFilter] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [pending, startTransition] = useTransition();

  // Create form state
  const [planName, setPlanName] = useState(planNames[0] ?? '');
  const [note, setNote] = useState('');
  const [count, setCount] = useState('1');

  function copy(value: string) {
    navigator.clipboard.writeText(value);
    toast.success('Copied');
  }

  function create() {
    if (!planName) {
      toast.error('Pick a plan first (create one in Plans).');
      return;
    }
    startTransition(async () => {
      const n = Math.max(1, Math.min(50, Number(count) || 1));
      const res = await createKeyAction({ planName, note, count: n });
      if (!res.success) {
        toast.error(res.error);
        return;
      }
      toast.success(`Created ${res.created.length} key${res.created.length > 1 ? 's' : ''}`);
      setKeys((prev) => [...res.created, ...prev]);
      setShowCreate(false);
      setNote('');
      setCount('1');
      router.refresh();
    });
  }

  function toggleRevoke(id: string, current: boolean) {
    startTransition(async () => {
      const res = await toggleRevokeAction(id);
      if (!res.success) {
        toast.error(res.error);
        return;
      }
      setKeys((prev) => prev.map((k) => (k.id === id ? { ...k, revoked: !current } : k)));
      toast.success(current ? 'Key restored' : 'Key revoked');
    });
  }

  const filtered = filter
    ? keys.filter(
        (k) =>
          k.key.toLowerCase().includes(filter.toLowerCase()) ||
          k.note.toLowerCase().includes(filter.toLowerCase()) ||
          k.planName.toLowerCase().includes(filter.toLowerCase())
      )
    : keys;

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3 border-b border-border/60 p-4">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by key, note, plan…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="pl-10"
          />
        </div>
        <Button variant="gradient" onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4" />
          New keys
        </Button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-border/60 text-left text-xs uppercase tracking-wider text-muted-foreground">
            <tr>
              <th className="px-4 py-3">Key</th>
              <th className="px-4 py-3">Plan</th>
              <th className="px-4 py-3">Note</th>
              <th className="px-4 py-3">Used</th>
              <th className="px-4 py-3">Created</th>
              <th className="px-4 py-3">Expires</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-12 text-center text-muted-foreground">
                  {filter ? 'No keys match your search' : 'No keys yet — create one above'}
                </td>
              </tr>
            ) : (
              filtered.map((k) => (
                <tr key={k.id} className="border-b border-border/40 hover:bg-card/40">
                  <td className="px-4 py-3 font-mono text-xs">{k.key}</td>
                  <td className="px-4 py-3">
                    <Badge variant="outline">{k.planName}</Badge>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{k.note || '—'}</td>
                  <td className="px-4 py-3 tabular-nums">{k.totalUsed}</td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {formatRelative(k.createdAt)}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {k.expiresAt ? formatDate(k.expiresAt) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    {k.revoked ? (
                      <Badge variant="destructive">Revoked</Badge>
                    ) : k.expiresAt && new Date(k.expiresAt).getTime() < Date.now() ? (
                      <Badge variant="warning">Expired</Badge>
                    ) : (
                      <Badge variant="success">Active</Badge>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => copy(k.key)}
                        title="Copy"
                      >
                        <Copy className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => toggleRevoke(k.id, k.revoked)}
                        title={k.revoked ? 'Restore' : 'Revoke'}
                        disabled={pending}
                      >
                        {k.revoked ? (
                          <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
                        ) : (
                          <Ban className="h-3.5 w-3.5 text-destructive" />
                        )}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Generate access keys</DialogTitle>
            <DialogDescription>
              Each key inherits limits and expiry from the plan you select.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Plan</Label>
              {planNames.length === 0 ? (
                <p className="rounded-md border border-dashed border-border p-3 text-sm text-muted-foreground">
                  No plans yet. Create one in <strong>Plans</strong> first.
                </p>
              ) : (
                <Select value={planName} onValueChange={setPlanName}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {planNames.map((p) => (
                      <SelectItem key={p} value={p}>
                        {p}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>How many?</Label>
                <Input
                  type="number"
                  min={1}
                  max={50}
                  value={count}
                  onChange={(e) => setCount(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Note (optional)</Label>
                <Input
                  placeholder="Sold to: client X"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>
              Cancel
            </Button>
            <Button variant="gradient" onClick={create} disabled={pending}>
              {pending ? <Loader2 className="animate-spin" /> : <Check className="h-4 w-4" />}
              Generate
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
