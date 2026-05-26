import { readdirSync, statSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve, relative, join } from 'node:path';
import { createHash } from 'node:crypto';
import { deflateRawSync, crc32 } from 'node:zlib';

const root = resolve(import.meta.dirname, '..');
const distDir = resolve(root, 'dist');
const outFile = resolve(root, `bulk-gpt-extension-v${pkgVersion()}.zip`);

function pkgVersion() {
  return JSON.parse(readFileSync(resolve(root, 'package.json'), 'utf8')).version;
}

function walk(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    if (statSync(p).isDirectory()) walk(p, out);
    else out.push(p);
  }
  return out;
}

const files = walk(distDir).map((abs) => ({
  rel: relative(distDir, abs).split('\\').join('/'),
  data: readFileSync(abs),
}));

// Minimal zip writer (DEFLATE)
const localHeaders = [];
const central = [];
let offset = 0;

for (const f of files) {
  const compressed = deflateRawSync(f.data);
  const crc = crc32(f.data);
  const nameBytes = Buffer.from(f.rel, 'utf8');

  const local = Buffer.alloc(30 + nameBytes.length);
  local.writeUInt32LE(0x04034b50, 0);
  local.writeUInt16LE(20, 4);          // version needed
  local.writeUInt16LE(0, 6);            // flags
  local.writeUInt16LE(8, 8);            // compression: deflate
  local.writeUInt16LE(0, 10);           // mod time
  local.writeUInt16LE(0, 12);           // mod date
  local.writeUInt32LE(crc, 14);
  local.writeUInt32LE(compressed.length, 18);
  local.writeUInt32LE(f.data.length, 22);
  local.writeUInt16LE(nameBytes.length, 26);
  local.writeUInt16LE(0, 28);
  nameBytes.copy(local, 30);
  localHeaders.push(local, compressed);

  const cd = Buffer.alloc(46 + nameBytes.length);
  cd.writeUInt32LE(0x02014b50, 0);
  cd.writeUInt16LE(20, 4);              // version made by
  cd.writeUInt16LE(20, 6);              // version needed
  cd.writeUInt16LE(0, 8);
  cd.writeUInt16LE(8, 10);
  cd.writeUInt16LE(0, 12);
  cd.writeUInt16LE(0, 14);
  cd.writeUInt32LE(crc, 16);
  cd.writeUInt32LE(compressed.length, 20);
  cd.writeUInt32LE(f.data.length, 24);
  cd.writeUInt16LE(nameBytes.length, 28);
  cd.writeUInt16LE(0, 30);
  cd.writeUInt16LE(0, 32);
  cd.writeUInt16LE(0, 34);
  cd.writeUInt16LE(0, 36);
  cd.writeUInt32LE(0, 38);
  cd.writeUInt32LE(offset, 42);
  nameBytes.copy(cd, 46);
  central.push(cd);

  offset += local.length + compressed.length;
}

const cdSize = central.reduce((s, b) => s + b.length, 0);
const cdOffset = offset;

const eocd = Buffer.alloc(22);
eocd.writeUInt32LE(0x06054b50, 0);
eocd.writeUInt16LE(0, 4);
eocd.writeUInt16LE(0, 6);
eocd.writeUInt16LE(files.length, 8);
eocd.writeUInt16LE(files.length, 10);
eocd.writeUInt32LE(cdSize, 12);
eocd.writeUInt32LE(cdOffset, 16);
eocd.writeUInt16LE(0, 20);

const buf = Buffer.concat([...localHeaders, ...central, eocd]);
writeFileSync(outFile, buf);
console.log(`✓ Wrote ${outFile} (${(buf.length / 1024).toFixed(1)} KB)`);
