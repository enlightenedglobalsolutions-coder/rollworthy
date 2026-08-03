// ============================================================================
//  test_standards.js — the install prompt, the backup nudge, and the EGS
//  standing rules that are easy to break and quiet when broken.
//
//  INSTALL PROMPT
//  The manifest was never the reason there was no install prompt: the app met
//  every Chrome criterion and simply never listened for beforeinstallprompt.
//  These assertions pin the fix AND the two traps in it — a bare storage key
//  (which silenced Kept's banner across the shared origin) and iOS, which never
//  fires the event at all and would otherwise show nothing forever.
//
//  BACKUP NUDGE
//  The Aug-1 standard: only with real data, only at 21+ days or never, dismiss
//  snoozes 7 days. Thresholds are read out of the shipping source, so a typo
//  that turns 21 days into 21 hours fails here.
// ============================================================================
const fs = require('fs');
const path = require('path');

let p = 0, f = 0;
const ok = (n, c, x) => { c ? (p++, console.log("  PASS " + n))
                            : (f++, console.log("  FAIL " + n + (x === undefined ? "" : " [" + x + "]"))); };

const HERE = __dirname;
const HTML = fs.readFileSync(path.join(HERE, 'index.html'), 'utf8');

// ---- install prompt --------------------------------------------------------
ok("listens for beforeinstallprompt", /addEventListener\('beforeinstallprompt'/.test(HTML));
ok("suppresses Chrome's own UI with preventDefault", /e\.preventDefault\(\);/.test(HTML));
ok("keeps the deferred event", /deferredInstall=e;/.test(HTML));
ok("calls prompt() on the deferred event", /deferredInstall\.prompt\(\);/.test(HTML));
ok("awaits userChoice before clearing", /deferredInstall\.userChoice\.then/.test(HTML));
ok("listens for appinstalled", /addEventListener\('appinstalled'/.test(HTML));

// the shared-origin trap
ok("dismiss key is ft_-prefixed", /LS_INSTALL='ft_installDismissed'/.test(HTML));
ok("no BARE installPromptDismissed key anywhere",
   HTML.indexOf("'installPromptDismissed'") === -1);
ok("dismissal is persisted", /localStorage\.setItem\(LS_INSTALL,'1'\)/.test(HTML));
ok("a prior dismissal suppresses the banner",
   /if\(localStorage\.getItem\(LS_INSTALL\)\)return;/.test(HTML));

// the iOS trap
ok("iOS detected by feature, not user-agent",
   /function isIOSSafari\(\)\{return 'standalone' in navigator;\}/.test(HTML));
ok("no user-agent sniffing for platform",
   !/navigator\.userAgent/.test(HTML), "userAgent referenced");
ok("iOS gets the manual path instead of silence",
   /Tap Share, then/.test(HTML));
ok("iOS variant omits the Add button (no event to fire)",
   /\(mode==='prompt'\?'<button class="btn small primary" data-action="installGo">Add<\/button>':''\)/.test(HTML));

// don't nag the already-installed
ok("suppressed when already installed",
   /display-mode: standalone/.test(HTML) && /if\(isInstalled\(\)\)return;/.test(HTML));

// WHERE the banner may appear. The original report was "no install prompt on
// FIRST load", so the first-run landing screen is the case that matters most —
// it must NOT be gated behind company setup. But render() returns early when
// there is no cfg, so reaching the banner there needs its own call site; a
// guard change alone would silently do nothing.
ok("no cfg gate suppressing first load", !/if\(!cfg\)return;/.test(HTML));
ok("guard only blocks other screens once set up",
   /if\(cfg&&view\.name!=='home'\)return;/.test(HTML));
ok("first-run landing reaches the banner",
   /renderFirstRun\(\);\s*\n\s*maybeShowInstall\(\);/.test(HTML));
// the wizard never RAISES the banner. A banner already raised on the landing
// screen persists across navigation (same as the update/backup banners) — that
// is the observed behaviour, not a per-screen hide.
ok("the setup wizard never raises the banner",
   /if\(view\.name==='setup'\)\{renderSetup\(\);return;\}/.test(HTML));
ok("three call sites (event, render tail, first-run)",
   (HTML.match(/maybeShowInstall\(\);/g) || []).length === 3,
   (HTML.match(/maybeShowInstall\(\);/g) || []).length);

// ---- mutual exclusion: the banners share one slot --------------------------
ok("install yields to update + backup banners", /function bannerBusy\(\)/.test(HTML));
ok("bannerBusy checks BOTH other banners",
   /getElementById\('updateBanner'\)/.test(HTML) && /getElementById\('nudgeBanner'\)/.test(HTML));
ok("install checks bannerBusy before showing", /if\(bannerBusy\(\)\)return;/.test(HTML));
ok("backup nudge yields back to install",
   /if\(ib&&ib\.classList\.contains\('show'\)\)return;/.test(HTML));

// ---- backup nudge, the Aug-1 standard --------------------------------------
const nudge = /function maybeNudge\(\)\{[\s\S]*?\n\}/.exec(HTML);
ok("maybeNudge() found", !!nudge);
if (nudge) {
  const src = nudge[0];
  ok("nudges only when real data exists", /if\(!records\.length\)return;/.test(src));
  ok("threshold is 21 days, in ms", /21\*24\*3600\*1000/.test(src));
  ok("never-backed-up also triggers it", /!last\|\|/.test(src));
  ok("respects an active snooze", /if\(Date\.now\(\)<snooze\)return;/.test(src));
}
ok("dismiss snoozes 7 days", /LS_NUDGE,String\(Date\.now\(\)\+7\*24\*3600\*1000\)/.test(HTML));
ok("backup filename is rollworthy-backup-<date>.json",
   /'rollworthy-backup-'\+todayStr\(\)\+'\.json'/.test(HTML));

// ---- version stamp ---------------------------------------------------------
ok("two visible version stamps (home + Manager)",
   (HTML.match(/esc\(window\.EGS_VERSION\)/g) || []).length === 2);
ok("Manager stamp is identifiable", /id="mgr-version"/.test(HTML));
ok("version is stamped in the deploy-rewritable form",
   /window\.EGS_VERSION = '\d{4}\.\d{2}\.\d{2}-\d{4}';/.test(HTML));

// ---- safe area above the gesture bar ---------------------------------------
// body carries the bottom inset, so every normal-flow action row clears the bar.
ok("body pads for the bottom inset",
   /body\{[^}]*padding-bottom:calc\(env\(safe-area-inset-bottom\)/.test(HTML));
ok("header pads for the top inset",
   /padding:calc\(env\(safe-area-inset-top\)/.test(HTML));
// every element pinned to the bottom must clear the gesture bar itself
[['.banner', /\.banner\{[^}]*bottom:calc\(env\(safe-area-inset-bottom\)/],
 ['#toast', /#toast\{[^}]*bottom:calc\(env\(safe-area-inset-bottom\)/],
 ['#modal .sheet', /#modal \.sheet\{[^}]*calc\(env\(safe-area-inset-bottom\)/],
 ['#camWrap .bar', /#camWrap \.bar\{[^}]*calc\(env\(safe-area-inset-bottom\)/]]
  .forEach(([label, re]) => ok("bottom-pinned " + label + " clears the gesture bar", re.test(HTML)));

// ---- standing rules --------------------------------------------------------
ok("zero inline onclick", (HTML.match(/onclick=/g) || []).length === 0,
   (HTML.match(/onclick=/g) || []).length);

const spliceLines = HTML.split('\n')
  .map((line, i) => ({ line, n: i + 1 }))
  .filter((r) => r.line.indexOf('.splice(') !== -1);
const unguarded = spliceLines.filter((r) => r.line.indexOf('confirm(') === -1);
ok("every delete still confirm-guarded after today's edits (" + spliceLines.length + " checked)",
   unguarded.length === 0 && spliceLines.length >= 5, unguarded.map((r) => r.n).join(','));

console.log("\n" + p + " passed, " + f + " failed");
process.exit(f ? 1 : 0);
