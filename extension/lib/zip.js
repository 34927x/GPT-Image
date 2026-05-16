/* Minimal ZIP creator (store method, no compression) */
self.GPTZip = {
  create: async function(files) {
    // files: [{name: string, data: ArrayBuffer | Blob}]
    const processed = [];
    for (const f of files) {
      const data = f.data instanceof Blob ? await f.data.arrayBuffer() : f.data;
      processed.push({ name: f.name, data: new Uint8Array(data) });
    }

    const localHeaders = [];
    const centralEntries = [];
    let dataOffset = 0;

    for (const f of processed) {
      const nameBytes = strToU8(f.name);
      const crc = crc32(f.data);

      const localExtra = new Uint8Array(0);
      const local = buildLocalHeader(nameBytes, crc, f.data.length, localExtra);
      localHeaders.push({ data: local, name: nameBytes, crc, size: f.data.length });

      const central = buildCentralEntry(nameBytes, crc, f.data.length, dataOffset + local.length);
      centralEntries.push(central);
      dataOffset += local.length + f.data.length;
    }

    const parts = [];
    let centralOffset = dataOffset;
    for (let i = 0; i < processed.length; i++) {
      parts.push(localHeaders[i].data);
      parts.push(processed[i].data);
    }
    for (const ce of centralEntries) {
      parts.push(ce);
    }

    const eocd = buildEOCD(processed.length, dataOffset, parts.length - processed.length * 2);
    parts.push(eocd);

    const totalLen = parts.reduce((s, p) => s + p.length, 0);
    const result = new Uint8Array(totalLen);
    let pos = 0;
    for (const p of parts) {
      result.set(p, pos);
      pos += p.length;
    }
    return new Blob([result], { type: 'application/zip' });
  }
};

function strToU8(s) {
  return new TextEncoder().encode(s);
}

function u32ToBytes(v) {
  return new Uint8Array([v & 0xff, (v >> 8) & 0xff, (v >> 16) & 0xff, (v >> 24) & 0xff]);
}
function u16ToBytes(v) {
  return new Uint8Array([v & 0xff, (v >> 8) & 0xff]);
}

function buildLocalHeader(nameBytes, crc, size, extra) {
  const nameLen = nameBytes.length;
  const extraLen = extra.length;
  const buf = new Uint8Array(30 + nameLen + extraLen);
  buf.set([0x50, 0x4b, 0x03, 04], 0); // signature
  buf.set([0x0a, 0x00], 4); // version needed
  buf.set([0x00, 0x00], 6); // flags
  buf.set([0x00, 0x00], 8); // compression: store
  buf.set([0x00, 0x00, 0x00, 0x00], 10); // mod time/date
  buf.set(u32ToBytes(crc), 14);
  buf.set(u32ToBytes(size), 18); // compressed size
  buf.set(u32ToBytes(size), 22); // uncompressed size
  buf.set(u16ToBytes(nameLen), 26);
  buf.set(u16ToBytes(extraLen), 28);
  buf.set(nameBytes, 30);
  if (extraLen) buf.set(extra, 30 + nameLen);
  return buf;
}

function buildCentralEntry(nameBytes, crc, size, localOffset) {
  const nameLen = nameBytes.length;
  const comment = strToU8('GPT Rotator by TurabCoder');
  const commentLen = comment.length;
  const buf = new Uint8Array(46 + nameLen + commentLen);
  buf.set([0x50, 0x4b, 0x01, 0x02], 0); // signature
  buf.set([0x3f, 0x00], 4); // version made by
  buf.set([0x0a, 0x00], 6); // version needed
  buf.set([0x00, 0x00], 8); // flags
  buf.set([0x00, 0x00], 10); // compression
  buf.set([0x00, 0x00, 0x00, 0x00], 12); // mod time/date
  buf.set(u32ToBytes(crc), 16);
  buf.set(u32ToBytes(size), 20);
  buf.set(u32ToBytes(size), 24);
  buf.set(u16ToBytes(nameLen), 28);
  buf.set(u16ToBytes(0), 30); // extra len
  buf.set(u16ToBytes(commentLen), 32);
  buf.set(u16ToBytes(0), 34); // disk start
  buf.set([0x00, 0x00], 36); // internal attrs
  buf.set([0x00, 0x00, 0x00, 0x00], 38); // external attrs
  buf.set(u32ToBytes(localOffset), 42);
  buf.set(nameBytes, 46);
  buf.set(comment, 46 + nameLen);
  return buf;
}

function buildEOCD(count, centralOffset, centralSize) {
  const comment = strToU8('GPT Rotator by TurabCoder');
  const buf = new Uint8Array(22 + comment.length);
  buf.set([0x50, 0x4b, 0x05, 0x06], 0); // signature
  buf.set([0x00, 0x00], 4); // disk #
  buf.set([0x00, 0x00], 6); // disk with central
  buf.set(u16ToBytes(count), 8); // entries on disk
  buf.set(u16ToBytes(count), 10); // total entries
  buf.set(u32ToBytes(centralSize), 12); // central size
  buf.set(u32ToBytes(centralOffset), 16); // central offset
  buf.set(u16ToBytes(comment.length), 20);
  buf.set(comment, 22);
  return buf;
}

function crc32(data) {
  if (!crc32.table) {
    crc32.table = new Uint32Array(256);
    for (let i = 0; i < 256; i++) {
      let c = i;
      for (let j = 0; j < 8; j++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
      crc32.table[i] = c;
    }
  }
  let crc = 0xffffffff;
  for (let i = 0; i < data.length; i++) {
    crc = crc32.table[(crc ^ data[i]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}
