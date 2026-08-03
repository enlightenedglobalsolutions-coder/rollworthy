// ============================================================================
//  test_brand.js — the rename guard and the XSS escape guard.
//
//  WHAT THIS SUITE EXISTS FOR
//  Renaming Fleet Tracer -> Rollworthy is a find-and-replace across a 115KB
//  single-file app, and find-and-replace is exactly the operation that eats an
//  identifier it was never meant to touch. Four classes of string in this app
//  are LOAD-BEARING and must survive the rename untouched:
//
//    DB_NAME 'fleettracer'  — the IndexedDB store. Hard rule: never renamed.
//    ft_* localStorage keys — installed data, and every EGS app shares one
//                             origin, so these must stay unique (DECISIONS:52).
//    kind:'ft-*' markers    — the FILE WIRE FORMAT. handleImport() dispatches
//                             on these, not on the filename. Rename one and a
//                             manager's exported setup stops importing on a
//                             driver's phone.
//    'FTV1:'                — written into printed QR stickers and parsed by
//                             the scanner. Rename it and every sticker already
//                             on a windshield stops scanning.
//
//  esc() is RUN, not grepped — it is pulled out of index.html and executed
//  against real attack payloads, so what is tested is the code that ships.
// ============================================================================
const fs = require('fs');
const path = require('path');

let p = 0, f = 0;
const ok = (n, c, x) => { c ? (p++, console.log("  PASS " + n))
                            : (f++, console.log("  FAIL " + n + (x === undefined ? "" : " [" + x + "]"))); };

const HERE = __dirname;
const HTML = fs.readFileSync(path.join(HERE, 'index.html'), 'utf8');
const MANIFEST = JSON.parse(fs.readFileSync(path.join(HERE, 'manifest.webmanifest'), 'utf8'));

// ---- esc(): lift it out of the shipping file and run it --------------------
const escSrc = /^function esc\(s\)\{.*\}$/m.exec(HTML);
ok("esc() found in index.html", !!escSrc);
const esc = escSrc ? eval('(' + escSrc[0] + ')') : null;

if (esc) {
  ok("esc escapes <",  esc('<')  === '&lt;');
  ok("esc escapes >",  esc('>')  === '&gt;');
  ok("esc escapes \"", esc('"')  === '&quot;');
  ok("esc escapes '",  esc("'")  === '&#39;');
  ok("esc escapes &",  esc('&')  === '&amp;');
  ok("esc(null) is empty string", esc(null) === '');
  ok("esc(undefined) is empty string", esc(undefined) === '');

  // the two payloads that matter: a script injection and an attribute breakout
  const script = esc('<script>alert(1)</script>');
  ok("script payload is neutralised",
     script.indexOf('<') === -1 && script.indexOf('>') === -1, script);

  const breakout = esc('"><img src=x onerror=alert(1)>');
  ok("attribute-breakout payload is neutralised",
     breakout.indexOf('<') === -1 && breakout.indexOf('"') === -1, breakout);

  // a company name is echoed into the sticker and the header; it must not run
  ok("hostile company name cannot break out",
     esc("Acme'\"><script>").indexOf('<script') === -1);
}

// ---- the four protected identifier classes ---------------------------------
ok("IndexedDB name is still 'fleettracer'",
   /var DB_NAME='fleettracer'/.test(HTML));
ok("localStorage keys are still ft_*",
   /LS_CFG='ft_cfg'/.test(HTML) && /LS_REC='ft_records'/.test(HTML) &&
   /LS_RES='ft_res'/.test(HTML) && /LS_DRIVER='ft_driver'/.test(HTML) &&
   /LS_NUDGE='ft_nudge'/.test(HTML));
["ft-setup", "ft-records", "ft-backup"].forEach((k) =>
  ok("wire-format marker kind:'" + k + "' intact", HTML.indexOf("kind:'" + k + "'") !== -1));
ok("QR sticker prefix FTV1 is written and parsed",
   HTML.indexOf("'FTV1:'+v.id") !== -1 && HTML.indexOf("/^FTV1:(.+)$/") !== -1);

// ---- the rename actually happened ------------------------------------------
ok("no 'Fleet Tracer' left in index.html", HTML.indexOf('Fleet Tracer') === -1);
ok("no fleettracer-* export filenames left", HTML.indexOf('fleettracer-') === -1);
ok("export filenames are rollworthy-*",
   (HTML.match(/rollworthy-/g) || []).length === 4,
   (HTML.match(/rollworthy-/g) || []).length);
ok("<title> is Rollworthy", /<title>Rollworthy<\/title>/.test(HTML));
ok("manifest name is Rollworthy", MANIFEST.name === 'Rollworthy', MANIFEST.name);
ok("manifest short_name is Rollworthy", MANIFEST.short_name === 'Rollworthy', MANIFEST.short_name);

// ---- EGS standing rules ----------------------------------------------------
ok("zero inline onclick handlers",
   (HTML.match(/onclick=/g) || []).length === 0,
   (HTML.match(/onclick=/g) || []).length);

// every destructive splice must be guarded by a confirm on the same line
const spliceLines = HTML.split('\n')
  .map((line, i) => ({ line, n: i + 1 }))
  .filter((r) => r.line.indexOf('.splice(') !== -1);
ok("destructive splices exist to check", spliceLines.length > 0, spliceLines.length);
const unguarded = spliceLines.filter((r) => r.line.indexOf('confirm(') === -1);
ok("every delete is confirm-guarded (" + spliceLines.length + " checked)",
   unguarded.length === 0, unguarded.map((r) => r.n).join(','));

// ---- every icon the manifest promises is really on disk --------------------
MANIFEST.icons.forEach((ic) =>
  ok("manifest icon exists: " + ic.src, fs.existsSync(path.join(HERE, ic.src))));
const appleTouch = /<link rel="apple-touch-icon" href="([^"]+)"/.exec(HTML);
ok("apple-touch-icon exists on disk",
   !!appleTouch && fs.existsSync(path.join(HERE, appleTouch[1])),
   appleTouch && appleTouch[1]);

console.log("\n" + p + " passed, " + f + " failed");
process.exit(f ? 1 : 0);
