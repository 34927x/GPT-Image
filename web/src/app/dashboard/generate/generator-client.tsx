'use client';

import { useEffect, useState, useTransition, useCallback } from 'react';
import { Wand2, Upload, X, CheckCircle2, AlertCircle, Loader2, Clock } from 'lucide-react';
import { toast } from 'sonner';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { cn, truncate } from '@/lib/utils';
import type { JobStatus } from '@/lib/types';

type Size = '1:1' | '16:9' | '9:16' | '4:3';

interface JobView {
  id: string;
  prompt: string;
  status: JobStatus;
  imageUrl?: string;
  error?: string;
}

const STATUS_META: Record<JobStatus, { label: string; icon: React.ComponentType<{ className?: string }>; color: string }> = {
  pending: { label: 'Pending', icon: Clock, color: 'text-muted-foreground' },
  processing: { label: 'Processing', icon: Loader2, color: 'text-amber-400' },
  done: { label: 'Done', icon: CheckCircle2, color: 'text-emerald-400' },
  failed: { label: 'Failed', icon: AlertCircle, color: 'text-destructive' },
};

export function GeneratorClient() {
  const [prompts, setPrompts] = useState('');
  const [size, setSize] = useState<Size>('1:1');
  const [jobs, setJobs] = useState<JobView[]>([]);
  const [isSubmitting, startSubmit] = useTransition();

  const parsePrompts = (raw: string): string[] => {
    const blocks = raw.split(/\n\s*\n/).map((s) => s.trim()).filter(Boolean);
    if (blocks.length >= 2) return blocks;
    return raw.split('\n').map((s) => s.trim()).filter(Boolean);
  };

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    file.text().then((text) => {
      setPrompts(text);
      toast.success(`Loaded ${file.name}`);
    });
    e.target.value = '';
  }

  function submit() {
    const list = parsePrompts(prompts);
    if (!list.length) {
      toast.error('Add at least one prompt');
      return;
    }

    startSubmit(async () => {
      const res = await fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompts: list, size }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        toast.error(data.error ?? 'Failed to queue jobs');
        return;
      }
      const newJobs: JobView[] = data.jobs.map((j: { id: string; prompt: string }) => ({
        id: j.id,
        prompt: j.prompt,
        status: 'pending',
      }));
      setJobs((prev) => [...newJobs, ...prev]);
      setPrompts('');
      toast.success(`${list.length} job${list.length > 1 ? 's' : ''} queued`);
    });
  }

  // Poll for updates
  const pollJobs = useCallback(async () => {
    const active = jobs.filter((j) => j.status === 'pending' || j.status === 'processing');
    if (!active.length) return;
    const ids = active.map((j) => j.id).join(',');
    try {
      const res = await fetch(`/api/jobs/status?ids=${ids}`, { cache: 'no-store' });
      if (!res.ok) return;
      const data = await res.json();
      if (!Array.isArray(data.jobs)) return;
      setJobs((prev) =>
        prev.map((j) => {
          const update = data.jobs.find((u: { id: string }) => u.id === j.id);
          return update ? { ...j, ...update } : j;
        })
      );
    } catch {
      // network error, retry next tick
    }
  }, [jobs]);

  useEffect(() => {
    const id = setInterval(pollJobs, 2500);
    return () => clearInterval(id);
  }, [pollJobs]);

  function clearDone() {
    setJobs((prev) => prev.filter((j) => j.status !== 'done'));
  }

  const total = jobs.length;
  const done = jobs.filter((j) => j.status === 'done').length;
  const failed = jobs.filter((j) => j.status === 'failed').length;
  const progress = total ? ((done + failed) / total) * 100 : 0;
  const promptCount = parsePrompts(prompts).length;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
      {/* INPUT */}
      <Card>
        <CardContent className="space-y-5 p-6">
          <div className="space-y-2">
            <Label htmlFor="prompts">Prompts</Label>
            <Textarea
              id="prompts"
              value={prompts}
              onChange={(e) => setPrompts(e.target.value)}
              placeholder={'a cute cat\n\na futuristic city\nneon cyberpunk street'}
              rows={12}
              disabled={isSubmitting}
              className="font-mono"
            />
            <p className="text-xs text-muted-foreground">
              One per line, or separate multi-line prompts with a blank line.
              {promptCount > 0 && (
                <span className="ml-2 text-foreground">
                  {promptCount} prompt{promptCount > 1 ? 's' : ''} detected
                </span>
              )}
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Size</Label>
              <Select value={size} onValueChange={(v) => setSize(v as Size)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1:1">⬜ Square (1:1)</SelectItem>
                  <SelectItem value="16:9">🖥️ Wide (16:9)</SelectItem>
                  <SelectItem value="9:16">📱 Portrait (9:16)</SelectItem>
                  <SelectItem value="4:3">📺 Classic (4:3)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Upload .txt</Label>
              <label
                htmlFor="file"
                className="flex h-10 cursor-pointer items-center justify-center gap-2 rounded-md border border-dashed border-border bg-input/30 px-3 text-sm text-muted-foreground transition-colors hover:bg-input/50"
              >
                <Upload className="h-4 w-4" />
                Choose file
              </label>
              <input
                id="file"
                type="file"
                accept=".txt"
                onChange={onFile}
                className="hidden"
              />
            </div>
          </div>

          <Button
            onClick={submit}
            variant="gradient"
            size="lg"
            className="w-full"
            disabled={isSubmitting || !prompts.trim()}
          >
            {isSubmitting ? (
              <Loader2 className="animate-spin" />
            ) : (
              <>
                <Wand2 className="h-4 w-4" />
                Generate {promptCount > 1 ? `${promptCount} images` : 'image'}
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* QUEUE */}
      <Card>
        <CardContent className="p-6">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="font-semibold">Live queue</h3>
              <p className="text-xs text-muted-foreground">
                {total > 0
                  ? `${done} done · ${failed} failed · ${total - done - failed} remaining`
                  : 'Your jobs will appear here'}
              </p>
            </div>
            {jobs.some((j) => j.status === 'done') && (
              <Button variant="ghost" size="sm" onClick={clearDone}>
                <X className="h-3 w-3" />
                Clear done
              </Button>
            )}
          </div>

          {total > 0 && <Progress value={progress} className="mb-4 h-1.5" />}

          <div className="max-h-[600px] space-y-2 overflow-y-auto pr-1">
            <AnimatePresence initial={false}>
              {jobs.length === 0 ? (
                <div className="grid place-items-center rounded-lg border border-dashed border-border/60 py-16 text-center text-sm text-muted-foreground">
                  Submit prompts to get started.
                </div>
              ) : (
                jobs.map((j) => <JobRow key={j.id} job={j} />)
              )}
            </AnimatePresence>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function JobRow({ job }: { job: JobView }) {
  const meta = STATUS_META[job.status];
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: 8 }}
      className={cn(
        'flex items-center gap-3 rounded-lg border bg-card/40 p-3 transition-colors',
        job.status === 'done' && 'border-emerald-500/30',
        job.status === 'failed' && 'border-destructive/40',
        (job.status === 'pending' || job.status === 'processing') && 'border-border/60'
      )}
    >
      {job.imageUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={job.imageUrl}
          alt={job.prompt}
          className="h-12 w-12 shrink-0 rounded object-cover"
        />
      ) : (
        <div className="grid h-12 w-12 shrink-0 place-items-center rounded bg-muted/40">
          <meta.icon
            className={cn(
              'h-4 w-4',
              meta.color,
              job.status === 'processing' && 'animate-spin'
            )}
          />
        </div>
      )}

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{truncate(job.prompt, 80)}</p>
        {job.error && (
          <p className="truncate text-xs text-destructive">{job.error}</p>
        )}
      </div>

      <Badge
        variant={
          job.status === 'done'
            ? 'success'
            : job.status === 'failed'
            ? 'destructive'
            : job.status === 'processing'
            ? 'warning'
            : 'outline'
        }
        className="shrink-0"
      >
        {meta.label}
      </Badge>
    </motion.div>
  );
}
