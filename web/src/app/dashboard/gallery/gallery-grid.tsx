'use client';

import { useState } from 'react';
import { Download, Maximize2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { formatRelative } from '@/lib/utils';

interface Item {
  id: string;
  url: string;
  prompt: string;
  createdAt: string;
}

export function GalleryGrid({ items }: { items: Item[] }) {
  const [active, setActive] = useState<Item | null>(null);

  async function download(item: Item) {
    try {
      const res = await fetch(item.url);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${item.prompt.replace(/[^a-z0-9]+/gi, '-').slice(0, 40) || 'image'}.png`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      window.open(item.url, '_blank');
    }
  }

  return (
    <>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
        <AnimatePresence initial={false}>
          {items.map((it) => (
            <motion.button
              key={it.id}
              layout
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              onClick={() => setActive(it)}
              className="group relative aspect-square overflow-hidden rounded-lg border border-border/60 bg-card/40 transition-all hover:border-primary/40"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={it.url}
                alt={it.prompt}
                loading="lazy"
                className="h-full w-full object-cover transition-transform group-hover:scale-105"
              />
              <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/85 via-black/0 to-transparent opacity-0 transition-opacity group-hover:opacity-100">
                <div className="absolute bottom-0 w-full p-2 text-left">
                  <p className="line-clamp-2 text-xs font-medium text-white">
                    {it.prompt}
                  </p>
                  <p className="text-[10px] text-white/70">
                    {formatRelative(it.createdAt)}
                  </p>
                </div>
                <div className="absolute right-2 top-2 grid place-items-center rounded-md bg-black/50 p-1.5">
                  <Maximize2 className="h-3.5 w-3.5 text-white" />
                </div>
              </div>
            </motion.button>
          ))}
        </AnimatePresence>
      </div>

      <Dialog open={!!active} onOpenChange={(o) => !o && setActive(null)}>
        <DialogContent className="max-w-3xl">
          <DialogTitle className="sr-only">Image preview</DialogTitle>
          <DialogDescription className="sr-only">
            {active?.prompt}
          </DialogDescription>
          {active && (
            <div className="space-y-4">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={active.url}
                alt={active.prompt}
                className="max-h-[70vh] w-full rounded-lg object-contain"
              />
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{active.prompt}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatRelative(active.createdAt)}
                  </p>
                </div>
                <Button variant="gradient" onClick={() => download(active)}>
                  <Download className="h-4 w-4" />
                  Download
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
