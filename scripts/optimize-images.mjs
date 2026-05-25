// Resize + convert source images to WebP.
// Usage: node scripts/optimize-images.mjs [maxWidth] [quality]
// Defaults: maxWidth=2400, quality=82
// Looks for entries in TARGETS below and writes <name>.webp next to each source.
// Headshot stays PNG (for broad social-share/OG compatibility) and is just recompressed/resized.

import sharp from "sharp";
import { readFile, writeFile, stat } from "node:fs/promises";
import { resolve } from "node:path";

const DIR = "public/images";
const MAX = Number(process.argv[2]) || 2400;
const QUALITY = Number(process.argv[3]) || 82;

// Files to convert to webp
const TO_WEBP = [
  "geneeditingfull.png",
  "PHR2.png",
  "adaptatorfull.png",
  "tcplot(whale).png",
  "MarsSocietyPoster3.16.25.jpg",
  "tcplot(colorswithtext).png",
  "tcplot(petriwithtext).png",
  "tcplot(octopuschartswithtext).png",
  "venus1.png",
];

// Files to recompress in place (kept as PNG for OG/social compatibility)
const PNG_RECOMPRESS = [
  { file: "headshot.png", max: 1200 },
];

function fmt(bytes) {
  if (bytes >= 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + " MB";
  return (bytes / 1024).toFixed(0) + " KB";
}

async function sizeOf(path) {
  try { return (await stat(path)).size; } catch { return 0; }
}

async function convertWebp(name) {
  const src = resolve(DIR, name);
  const out = src.replace(/\.(png|jpe?g)$/i, ".webp");
  const before = await sizeOf(src);
  const buf = await sharp(src)
    .resize({ width: MAX, height: MAX, fit: "inside", withoutEnlargement: true })
    .webp({ quality: QUALITY })
    .toBuffer();
  await writeFile(out, buf);
  const after = buf.length;
  const pct = before ? Math.round((1 - after / before) * 100) : 0;
  console.log(`${name.padEnd(38)} ${fmt(before).padStart(8)} → ${fmt(after).padStart(8)}  (-${pct}%)`);
}

async function recompressPng({ file, max }) {
  const src = resolve(DIR, file);
  const before = await sizeOf(src);
  const buf = await sharp(src)
    .resize({ width: max, height: max, fit: "inside", withoutEnlargement: true })
    .png({ compressionLevel: 9, palette: true })
    .toBuffer();
  await writeFile(src, buf);
  const after = buf.length;
  const pct = before ? Math.round((1 - after / before) * 100) : 0;
  console.log(`${file.padEnd(38)} ${fmt(before).padStart(8)} → ${fmt(after).padStart(8)}  (-${pct}%) [png]`);
}

console.log(`Resizing to max ${MAX}px, webp quality ${QUALITY}\n`);
for (const f of TO_WEBP) await convertWebp(f);
for (const p of PNG_RECOMPRESS) await recompressPng(p);
console.log("\nDone. Update <img src> references from .png/.jpg to .webp for the converted files.");
