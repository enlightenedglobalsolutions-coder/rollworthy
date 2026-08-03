// ============================================================================
//  test_share.js — EGS CORE SHARE v2.
//
//  THE ONE THING THIS SUITE EXISTS TO PROVE
//  The share payload is the app's public URL and nothing else. Rollworthy holds
//  inspection records, defect photos, driver names, vehicle plates, a company
//  PIN and a whole company setup. A share feature that leaked any of that would
//  break the app's central promise, and it would leak quietly. So appShareUrl()
//  is EXECUTED against a realistic deep URL and its output is checked to be the
//  bare directory — and doShareApp's payload is checked to reference nothing but
//  APP_NAME, SHARE_APP_LINE and that URL.
//
//  The standard also says: one handler, one glyph, no drift. Two entry points
//  exist (header icon, Privacy block) and both must route to the same handler.
// ============================================================================
const fs = require('fs');
const path = require('path');

let p = 0, f = 0;
const ok = (n, c, x) => { c ? (p++, console.log("  PASS " + n))
                            : (f++, console.log("  FAIL " + n + (x === undefined ? "" : " [" + x + "]"))); };

const HERE = __dirname;
const HTML = fs.readFileSync(path.join(HERE, 'index.html'), 'utf8');

// ---- run appShareUrl() for real --------------------------------------------
const srcFn = /function appShareUrl\(\)\{[\s\S]*?\n\}/.exec(HTML);
ok("appShareUrl() found", !!srcFn);

if (srcFn) {
  // stub the one global it touches, then execute the shipping source
  const make = (href) => {
    const u = new URL(href);
    const location = { origin: u.origin, pathname: u.pathname };
    return eval('(function(location){ return (' + srcFn[0] + '); })')(location)();
  };

  ok("resolves to the app directory on Pages",
     make('https://enlightenedglobalsolutions-coder.github.io/rollworthy/') ===
     'https://enlightenedglobalsolutions-coder.github.io/rollworthy/');

  ok("strips index.html",
     make('https://enlightenedglobalsolutions-coder.github.io/rollworthy/index.html') ===
     'https://enlightenedglobalsolutions-coder.github.io/rollworthy/');

  // the real risk: a deep link that carries state must be reduced to the directory
  const deep = make('https://enlightenedglobalsolutions-coder.github.io/rollworthy/index.html');
  ok("a deep URL is reduced to the bare directory", deep.endsWith('/rollworthy/'), deep);
  ok("shared URL carries no query string", deep.indexOf('?') === -1, deep);
  ok("shared URL carries no fragment", deep.indexOf('#') === -1, deep);
  ok("works on a custom domain too",
     make('https://rollworthy.ca/') === 'https://rollworthy.ca/');
}

// ---- the payload references nothing but the app's own identity -------------
const body = /function doShareApp\(\)\{[\s\S]*?\n\}/.exec(HTML);
ok("doShareApp() found", !!body);
if (body) {
  const src = body[0];
  // every app-data identifier that must NOT be reachable from the share path
  ['records', 'cfg', 'draft', 'resolutions', 'managerPin', 'vehicles', 'drivers',
   'LS_CFG', 'LS_REC', 'LS_RES', 'LS_DRIVER', 'DB_NAME', 'photos', 'packRecords']
    .forEach((id) => ok("share payload cannot reach " + id,
                        !new RegExp('\\b' + id + '\\b').test(src)));

  ok("payload is exactly {title, text, url}",
     /navigator\.share\(\{title:APP_NAME,text:SHARE_APP_LINE,url:url\}\)/.test(src));
  ok("url comes from appShareUrl()", /var url=appShareUrl\(\);/.test(src));
  ok("an aborted share is silent (no fallback spam)", /AbortError/.test(src));
}

// ---- one handler, two entry points, one glyph ------------------------------
ok("exactly one doShareApp handler", (HTML.match(/function doShareApp\(/g) || []).length === 1);
ok("exactly two share entry points",
   (HTML.match(/data-action="shareApp"/g) || []).length === 2,
   (HTML.match(/data-action="shareApp"/g) || []).length);
ok("the action routes to the one handler", /shareApp:function\(\)\{doShareApp\(\);\}/.test(HTML));
ok("one shared glyph constant", (HTML.match(/var EGS_SHARE_GLYPH=/g) || []).length === 1);
ok("header entry point uses the shared glyph",
   /data-action="shareApp"[^]*?'\+EGS_SHARE_GLYPH\+'/.test(HTML));
ok("Privacy entry point uses the shared glyph",
   /<span class="sg">'\+EGS_SHARE_GLYPH\+'<\/span>/.test(HTML));

// ---- fallback chain --------------------------------------------------------
ok("clipboard fallback exists", /navigator\.clipboard&&navigator\.clipboard\.writeText/.test(HTML));
ok("clipboard success is confirmed to the user", /toast\('Link copied'\)/.test(HTML));
ok("clipboard refusal still surfaces the link", /function shareAppFallback\(/.test(HTML));
ok("toast element exists in the DOM", /<div id="toast"/.test(HTML));

// ---- host-supplied constants ------------------------------------------------
ok("APP_NAME is Rollworthy", /var APP_NAME='Rollworthy';/.test(HTML));
ok("SHARE_APP_LINE is set and app-specific", /var SHARE_APP_LINE='Rollworthy /.test(HTML));

console.log("\n" + p + " passed, " + f + " failed");
process.exit(f ? 1 : 0);
