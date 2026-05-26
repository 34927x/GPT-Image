'use client';

import { useState } from 'react';
import { Download, Maximize2, Archive, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'sonner';
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
  const [zipping, setZipping] = useState(false);

  function downloadOne(item: Item) {
    const a = document.createElement('a');
    a.href = item.url;
    a.download = filenameFor(item.prompt, item.id);
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  async function downloadAllZip() {
    if (zipping) return;
    setZipping(true);
    try {
      // Use a dynamic import so the JSZip-like helper only loads on demand
      const buf = await buildZip(items);
      const blob = new Blob([new Uint8Array(buf)], { type: 'application/zip' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `bulk-gpt-${Date.now()}.zip`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
      toast.success(`Downloaded ${items.length} images`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Zip failed');
    }
    setZipping(false);
  }

  return (
    <>
      <div className="mb-4 flex justify-end">
        <Button variant="outline" onClick={downloadAllZip} disabled={zipping || items.length === 0}>
          {zipping ? <Loader2 className="animate-spin" /> : <Archive className="h-4 w-4" />}
          Download all as ZIP
        </Button>
      </div>

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
                <Button variant="gradient" onClick={() => downloadOne(active)}>
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

function filenameFor(prompt: string, id: string): string {
  const slug = prompt.replace(/[^a-z0-9]+/gi, '-').slice(0, 40) || 'image';
  return `${slug}-${id.slice(-6)}.png`;
}

/** Minimal STORE-method ZIP writer (no compression, browser-safe). */
async function buildZip(items: Item[]): Promise<Uint8Array> {
  const enc = new TextEncoder();
  const files: { name: Uint8Array; data: Uint8Array; crc: number }[] = [];

  for (const it of items) {
    const data = await dataUrlToBytes(it.url);
    files.push({
      name: enc.encode(filenameFor(it.prompt, it.id)),
      data,
      crc: crc32(data),
    });
  }

  const localChunks: Uint8Array[] = [];
  const central: Uint8Array[] = [];
  let offset = 0;

  for (const f of files) {
    const local = new Uint8Array(30 + f.name.length);
    const dv = new DataView(local.buffer);
    dv.setUint32(0, 0x04034b50, true);
    dv.setUint16(4, 20, true);
    dv.setUint16(6, 0, true);
    dv.setUint16(8, 0, true);
    dv.setUint16(10, 0, true);
    dv.setUint16(12, 0, true);
    dv.setUint32(14, f.crc, true);
    dv.setUint32(18, f.data.length, true);
    dv.setUint32(22, f.data.length, true);
    dv.setUint16(26, f.name.length, true);
    dv.setUint16(28, 0, true);
    local.set(f.name, 30);
    localChunks.push(local, f.data);

    const cd = new Uint8Array(46 + f.name.length);
    const cdv = new DataView(cd.buffer);
    cdv.setUint32(0, 0x02014b50, true);
    cdv.setUint16(4, 20, true);
    cdv.setUint16(6, 20, true);
    cdv.setUint16(8, 0, true);
    cdv.setUint16(10, 0, true);
    cdv.setUint16(12, 0, true);
    cdv.setUint16(14, 0, true);
    cdv.setUint32(16, f.crc, true);
    cdv.setUint32(20, f.data.length, true);
    cdv.setUint32(24, f.data.length, true);
    cdv.setUint16(28, f.name.length, true);
    cdv.setUint16(30, 0, true);
    cdv.setUint16(32, 0, true);
    cdv.setUint16(34, 0, true);
    cdv.setUint16(36, 0, true);
    cdv.setUint32(38, 0, true);
    cdv.setUint32(42, offset, true);
    cd.set(f.name, 46);
    central.push(cd);

    offset += local.length + f.data.length;
  }

  const cdSize = central.reduce((s, b) => s + b.length, 0);
  const cdOffset = offset;

  const eocd = new Uint8Array(22);
  const ev = new DataView(eocd.buffer);
  ev.setUint32(0, 0x06054b50, true);
  ev.setUint16(8, files.length, true);
  ev.setUint16(10, files.length, true);
  ev.setUint32(12, cdSize, true);
  ev.setUint32(16, cdOffset, true);

  const totalLen =
    localChunks.reduce((s, b) => s + b.length, 0) + cdSize + eocd.length;
  const out = new Uint8Array(totalLen);
  let p = 0;
  for (const chunk of [...localChunks, ...central, eocd]) {
    out.set(chunk, p);
    p += chunk.length;
  }
  return out;
}

async function dataUrlToBytes(url: string): Promise<Uint8Array> {
  const res = await fetch(url);
  return new Uint8Array(await res.arrayBuffer());
}

function crc32(data: Uint8Array): number {
  let table = (crc32 as unknown as { table?: Uint32Array }).table;
  if (!table) {
    table = new Uint32Array(256);
    for (let i = 0; i < 256; i++) {
      let c = i;
      for (let j = 0; j < 8; j++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      table[i] = c;
    }
    (crc32 as unknown as { table: Uint32Array }).table = table;
  }
  let crc = 0xffffffff;
  for (let i = 0; i < data.length; i++) {
    crc = table[(crc ^ data[i]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}
