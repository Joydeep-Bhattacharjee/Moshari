// Minimal ZIP writer (stored, no compression) for the browser's "Generate all 60" download.
// No dependency and no network: the pack is built in memory from the live scenario.

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c >>> 0;
  }
  return table;
})();

export function crc32(bytes: Uint8Array): number {
  let c = 0xffffffff;
  for (const b of bytes) c = CRC_TABLE[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

export interface ZipEntry {
  name: string;
  content: string;
}

const DOS_DATE_1980_01_01 = (0 << 9) | (1 << 5) | 1; // fixed date: same entries give the same bytes
const UTF8_FLAG = 0x0800;

export function buildZip(entries: ZipEntry[]): Uint8Array<ArrayBuffer> {
  const encoder = new TextEncoder();
  const files = entries.map((e) => ({ name: encoder.encode(e.name), data: encoder.encode(e.content) }));
  const size = files.reduce((s, f) => s + 30 + f.name.length + f.data.length + 46 + f.name.length, 22);
  const out = new Uint8Array(size);
  const view = new DataView(out.buffer);
  let offset = 0;
  const central: { name: Uint8Array; crc: number; length: number; at: number }[] = [];
  const header = (signature: number) => view.setUint32(offset, signature, true);
  for (const f of files) {
    const crc = crc32(f.data);
    central.push({ name: f.name, crc, length: f.data.length, at: offset });
    header(0x04034b50);
    view.setUint16(offset + 4, 20, true);
    view.setUint16(offset + 6, UTF8_FLAG, true);
    view.setUint16(offset + 12, DOS_DATE_1980_01_01, true);
    view.setUint32(offset + 14, crc, true);
    view.setUint32(offset + 18, f.data.length, true);
    view.setUint32(offset + 22, f.data.length, true);
    view.setUint16(offset + 26, f.name.length, true);
    out.set(f.name, offset + 30);
    out.set(f.data, offset + 30 + f.name.length);
    offset += 30 + f.name.length + f.data.length;
  }
  const centralStart = offset;
  for (const c of central) {
    header(0x02014b50);
    view.setUint16(offset + 4, 20, true);
    view.setUint16(offset + 6, 20, true);
    view.setUint16(offset + 8, UTF8_FLAG, true);
    view.setUint16(offset + 14, DOS_DATE_1980_01_01, true);
    view.setUint32(offset + 16, c.crc, true);
    view.setUint32(offset + 20, c.length, true);
    view.setUint32(offset + 24, c.length, true);
    view.setUint16(offset + 28, c.name.length, true);
    view.setUint32(offset + 42, c.at, true);
    out.set(c.name, offset + 46);
    offset += 46 + c.name.length;
  }
  header(0x06054b50);
  view.setUint16(offset + 8, central.length, true);
  view.setUint16(offset + 10, central.length, true);
  view.setUint32(offset + 12, offset - centralStart, true);
  view.setUint32(offset + 16, centralStart, true);
  return out;
}
