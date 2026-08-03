// ============================================================================
//  make_icons.js — placeholder Rollworthy icons, zero dependencies.
//
//  No ImageMagick, no PIL on this machine, so the glyph is rasterised from
//  signed-distance primitives and the PNG is encoded by hand over node's
//  built-in zlib. TEMPORARY: the final plank-letterform R with the helm-wheel
//  bowl replaces these.
//
//  Gold #D6A84B on charcoal #1A1E25, rounded-square, letter R.
// ============================================================================
const zlib = require('zlib');
const fs   = require('fs');
const path = require('path');

const GOLD     = [0xD6, 0xA8, 0x4B];
const CHARCOAL = [0x1A, 0x1E, 0x25];
const SS = 4;                       // supersample factor per axis (16 samples/px)

// ---- geometry helpers (all in normalised 0..1 space, y down) ----------------
const clamp0 = (v) => (v > 0 ? v : 0);

// signed distance to a rounded rect centred at (cx,cy), half-extents hx,hy
function sdRoundRect(px, py, cx, cy, hx, hy, r) {
  const dx = Math.abs(px - cx) - (hx - r);
  const dy = Math.abs(py - cy) - (hy - r);
  const ox = clamp0(dx), oy = clamp0(dy);
  return Math.sqrt(ox * ox + oy * oy) + Math.min(Math.max(dx, dy), 0) - r;
}

// signed distance to a capsule (thick line segment) from a->b, radius r
function sdCapsule(px, py, ax, ay, bx, by, r) {
  const pax = px - ax, pay = py - ay, bax = bx - ax, bay = by - ay;
  const denom = bax * bax + bay * bay;
  let h = denom === 0 ? 0 : (pax * bax + pay * bay) / denom;
  h = h < 0 ? 0 : h > 1 ? 1 : h;
  const dx = pax - bax * h, dy = pay - bay * h;
  return Math.sqrt(dx * dx + dy * dy) - r;
}

// inside an elliptical annulus, restricted to the right half (the R's bowl)
function inBowl(px, py, cx, cy, ax, ay, t) {
  if (px < cx) return false;
  const ox = (px - cx) / ax, oy = (py - cy) / ay;
  if (ox * ox + oy * oy > 1) return false;             // outside outer ellipse
  const ix = (px - cx) / (ax - t), iy = (py - cy) / (ay - t);
  return ix * ix + iy * iy >= 1;                       // inside the counter = hole
}

// ---- the R glyph -----------------------------------------------------------
// Built from a stem, an elliptical-annulus bowl welded to it, and a diagonal
// leg. Coordinates are normalised to a 0..1 glyph box, then scaled/centred.
const T  = 0.12;                    // stroke thickness
const CX = 0.375;                   // stem centre x, doubles as bowl centre
const BY = 0.335;                   // bowl centre y (bowl spans y 0.10 -> 0.57)

function inR(px, py) {
  if (sdRoundRect(px, py, CX, 0.50, T / 2, 0.40, T / 2) < 0) return true;   // stem
  if (inBowl(px, py, CX, BY, 0.325, 0.235, T)) return true;                 // bowl
  if (sdCapsule(px, py, 0.45, 0.53, 0.65, 0.90, T / 2) < 0) return true;    // leg
  return false;
}

// ---- PNG encoding ----------------------------------------------------------
const CRC_TABLE = (() => {
  const t = new Int32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c;
  }
  return t;
})();

function crc32(buf) {
  let c = 0xFFFFFFFF;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xFF] ^ (c >>> 8);
  return (c ^ 0xFFFFFFFF) >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length, 0);
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body), 0);
  return Buffer.concat([len, body, crc]);
}

function encodePNG(width, height, rgba) {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;    // bit depth
  ihdr[9] = 6;    // colour type: RGBA
  ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;

  // one filter byte (0 = None) per scanline
  const stride = width * 4;
  const raw = Buffer.alloc((stride + 1) * height);
  for (let y = 0; y < height; y++) {
    raw[y * (stride + 1)] = 0;
    rgba.copy(raw, y * (stride + 1) + 1, y * stride, (y + 1) * stride);
  }

  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]),
    chunk('IHDR', ihdr),
    chunk('IDAT', zlib.deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

// ---- render ----------------------------------------------------------------
// opts: { rounded, ring, glyphScale }
//   rounded   — rounded-square background with transparent corners
//   ring      — inset gold seal ring
//   glyphScale— glyph height as a fraction of the canvas (maskable needs
//               everything inside the central 80% safe zone)
function render(size, opts) {
  const { rounded = true, ring = true, glyphScale = 0.62 } = opts || {};
  const rgba = Buffer.alloc(size * size * 4);
  const bgRadius = 0.22;            // corner radius as fraction of size
  const ringInset = 0.085, ringHalf = 0.011;

  const gy = (1 - glyphScale) / 2;  // glyph vertical origin, centred

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      let r = 0, g = 0, b = 0, a = 0;

      for (let sy = 0; sy < SS; sy++) {
        for (let sx = 0; sx < SS; sx++) {
          const px = (x + (sx + 0.5) / SS) / size;
          const py = (y + (sy + 0.5) / SS) / size;

          let cr = 0, cg = 0, cb = 0, ca = 0;

          // background
          const inBg = rounded
            ? sdRoundRect(px, py, 0.5, 0.5, 0.5, 0.5, bgRadius) < 0
            : true;
          if (inBg) { cr = CHARCOAL[0]; cg = CHARCOAL[1]; cb = CHARCOAL[2]; ca = 255; }

          // gold seal ring
          if (inBg && ring) {
            const d = sdRoundRect(px, py, 0.5, 0.5, 0.5 - ringInset, 0.5 - ringInset,
                                  bgRadius - ringInset * 0.5);
            if (Math.abs(d) < ringHalf) { cr = GOLD[0]; cg = GOLD[1]; cb = GOLD[2]; ca = 255; }
          }

          // the R, mapped into the glyph box
          if (inBg) {
            const lx = (px - 0.5) / glyphScale + 0.5;
            const ly = (py - gy) / glyphScale;
            if (lx >= 0 && lx <= 1 && ly >= 0 && ly <= 1 && inR(lx, ly)) {
              cr = GOLD[0]; cg = GOLD[1]; cb = GOLD[2]; ca = 255;
            }
          }

          r += cr; g += cg; b += cb; a += ca;
        }
      }

      const n = SS * SS, i = (y * size + x) * 4;
      rgba[i]     = Math.round(r / n);
      rgba[i + 1] = Math.round(g / n);
      rgba[i + 2] = Math.round(b / n);
      rgba[i + 3] = Math.round(a / n);
    }
  }
  return encodePNG(size, size, rgba);
}

// ---- write -----------------------------------------------------------------
const OUT = process.argv[2];
if (!OUT) { console.error('usage: node make_icons.js <icons-dir>'); process.exit(1); }

const jobs = [
  // apple-touch: full-bleed square, iOS applies its own corner mask
  ['icon-180.png',           180, { rounded: false, ring: true,  glyphScale: 0.60 }],
  ['icon-192.png',           192, { rounded: true,  ring: true,  glyphScale: 0.60 }],
  ['icon-512.png',           512, { rounded: true,  ring: true,  glyphScale: 0.60 }],
  // maskable: full-bleed, glyph inside the central 80% safe zone, no ring
  // glyph half-diagonal at 0.55 is 0.334 < the 0.40 safe-circle radius
  ['icon-maskable-512.png',  512, { rounded: false, ring: false, glyphScale: 0.55 }],
];

for (const [name, size, opts] of jobs) {
  const buf = render(size, opts);
  fs.writeFileSync(path.join(OUT, name), buf);
  console.log(`  ${name.padEnd(24)} ${size}x${size}  ${buf.length} bytes`);
}
console.log('done');
