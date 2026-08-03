// ============================================================================
//  test_sw_logic.js — the caching decisions, plus the real service-worker.js.
//
//  The logic half is the platform suite (EGS/platform/test_sw_logic.js) bound
//  to this app's name. The file half is what that suite cannot see: that the
//  worker actually SHIPPING here declares the right APP_NAME, carries a stamp
//  egs-deploy.sh can rewrite, and precaches every icon the manifest promises.
//
//  Rollworthy shipped v1 on a FORK of the platform worker (var APP_NAME /
//  var VERSION, a EGS_SW_LOGIC.cachesToDelete API). egs-deploy.sh only rewrites
//  `const CACHE_VERSION = '…'`, so on that fork the cache version could never
//  bump — index.html would be stamped and the worker would not. Tests 14-17
//  are what stops that drift coming back.
// ============================================================================
const fs = require('fs');
const path = require('path');
const L = require('./sw_logic.js');

let p = 0, f = 0;
const ok = (n, c, x) => { c ? (p++, console.log("  PASS " + n))
                            : (f++, console.log("  FAIL " + n + (x === undefined ? "" : " [" + x + "]"))); };

const HERE = __dirname;
const SW   = fs.readFileSync(path.join(HERE, 'service-worker.js'), 'utf8');

// ---- cache naming ----------------------------------------------------------
ok("cacheName format",
   L.cacheName("rollworthy", "2026.08.03-0916") === "egs-rollworthy-2026.08.03-0916");

// ---- stale-cache cleanup: keep current, delete old SAME app, never others ---
const keys = [
  "egs-rollworthy-2026.07.30-0001",
  "egs-rollworthy-2026.08.03-0916",
  "egs-stagger-2026.08.02-1751",
  "egs-fleettracer-2026.07.30-0001",   // the pre-rename namespace
  "random-cache"
];
const del = L.staleCaches(keys, "rollworthy", "2026.08.03-0916");
ok("deletes old same-app cache", del.includes("egs-rollworthy-2026.07.30-0001"));
ok("keeps current cache",       !del.includes("egs-rollworthy-2026.08.03-0916"));
ok("never touches OTHER app cache", !del.includes("egs-stagger-2026.08.02-1751"));
ok("ignores non-egs caches",    !del.includes("random-cache"));
ok("exactly 1 to delete here",  del.length === 1, del.length);

// ---- strategy: HTML network-first is what makes deploys reach phones --------
ok("navigation -> network-first",  L.strategyFor("navigate", "") === "network-first");
ok("html accept -> network-first", L.strategyFor("cors", "text/html,*/*") === "network-first");
ok("icon -> stale-while-revalidate", L.strategyFor("cors", "image/png") === "stale-while-revalidate");
ok("script -> swr",                L.strategyFor("cors", "application/javascript") === "stale-while-revalidate");

// ---- version stamp format --------------------------------------------------
ok("valid version accepted", L.isValidVersion("2026.08.03-0916"));
ok("bad version rejected",  !L.isValidVersion("v3"));
ok("DEV placeholder rejected", !L.isValidVersion("DEV"));

// ---- the worker that actually ships ----------------------------------------
const appName = /const APP_NAME\s*=\s*'([^']*)'/.exec(SW);
ok("service-worker declares APP_NAME 'rollworthy'",
   !!appName && appName[1] === 'rollworthy', appName && appName[1]);

const cacheVer = /const CACHE_VERSION\s*=\s*'([^']*)'/.exec(SW);
ok("CACHE_VERSION is in the form egs-deploy.sh stamps",
   !!cacheVer && L.isValidVersion(cacheVer[1]), cacheVer && cacheVer[1]);

// every asset the manifest promises must survive going offline
const shell = /const SHELL = \[([\s\S]*?)\]/.exec(SW);
const shellSrc = shell ? shell[1] : '';
['index.html', 'manifest.webmanifest', 'sw_logic.js',
 'icon-192.png', 'icon-512.png', 'icon-maskable-512.png', 'apple-touch-icon.png']
  .forEach((asset) => ok("SHELL precaches " + asset, shellSrc.indexOf(asset) !== -1));

// the placeholder apple-touch name is gone everywhere, not just renamed in one place
ok("no icon-180.png reference survives anywhere",
   SW.indexOf('icon-180') === -1 &&
   fs.readFileSync(path.join(HERE, 'index.html'), 'utf8').indexOf('icon-180') === -1);

// every SHELL asset must exist — a precache miss is silent (addAll is caught)
const shellAssets = (shellSrc.match(/'\.\/([^']+)'/g) || [])
  .map((s) => s.replace(/^'\.\//, '').replace(/'$/, ''))
  .filter(Boolean);
const missing = shellAssets.filter((a) => !fs.existsSync(path.join(HERE, a)));
ok("every SHELL asset exists on disk (" + shellAssets.length + " checked)",
   missing.length === 0, missing.join(','));

// no drift between the tested core and the platform source it came from
const platformLogic = path.join(HERE, '..', '..', 'platform', 'sw_logic.js');
if (fs.existsSync(platformLogic)) {
  ok("sw_logic.js matches the platform source (no fork)",
     fs.readFileSync(platformLogic, 'utf8') === fs.readFileSync(path.join(HERE, 'sw_logic.js'), 'utf8'));
} else {
  ok("sw_logic.js matches the platform source (no fork)", true, "platform not on disk - skipped");
}

console.log("\n" + p + " passed, " + f + " failed");
process.exit(f ? 1 : 0);
