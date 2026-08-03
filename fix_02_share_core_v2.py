#!/usr/bin/env python3
"""
Rollworthy — Fix 02: EGS CORE SHARE v2.

Run from the same folder as index.html:
    python3 fix_02_share_core_v2.py

Ports the share-the-app standard from Notebuilt, the reference v2
implementation. Two entry points — the landing-header icon and the
Privacy-page block — both call ONE handler, doShareApp(), which can only
ever send appShareUrl(): the app's own directory URL. No record, photo,
vehicle, driver, PIN or company setting is reachable from it. That is the
whole point of the standard and test_share.js asserts it.

Adapted where Rollworthy has no equivalent of Notebuilt's helpers:
Notebuilt's sheet() becomes showModal(), and toast() is added here because
Rollworthy had none. The glyph, the handler, the URL and the payload rule
are unchanged.

Two deliberate departures from Notebuilt's layout, both agreed:
  * the block lives on the Privacy page, not a Support page — this is a
    B2B build with no Contribute/payment apparatus by design;
  * the header icon sits beside the hamburger, because Rollworthy's
    landing header has no search field (#vehSearch is on the vehicle-pick
    screen, not home).

Backs up first, exact-match anchors, ==1 guard, atomic, node --check.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HTML = Path("index.html")
MARKER = "EGS CORE — SHARE · v2"  # already-applied guard

# ---------------------------------------------------------------- constants
A_CONST = ("var LS_CFG='ft_cfg', LS_REC='ft_records', LS_RES='ft_res', "
           "LS_DRIVER='ft_driver', LS_NUDGE='ft_nudge';")
R_CONST = A_CONST + """

/* Host-supplied by the EGS core blocks. APP_NAME is the display name;
   SHARE_APP_LINE is this app's own one-line pitch, and the ONLY prose that
   should differ between apps carrying the core share block. */
var APP_NAME='Rollworthy';
var SHARE_APP_LINE='Rollworthy \\u2014 vehicle check-out & inspection records that stay on your phone.';"""

# ------------------------------------------------------------- the core block
A_CORE = "/* ---------- modal ---------- */"
R_CORE = """/* ============================================================
   EGS CORE — SHARE · v2
   Ported from Notebuilt, the reference v2 implementation. Do not
   edit this block per-app — only APP_NAME and SHARE_APP_LINE
   (near the top of the file) carry app-specific content.
   ============================================================ */

/* Feather "share-2", the glyph WFD uses — stroked currentColor so it takes
   the host app's icon colour. */
var EGS_SHARE_GLYPH='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>';

function appShareUrl(){
  /* the app's own directory URL, never a deep link into any state */
  return location.origin+location.pathname.replace(/[^/]*$/,'');
}

/* The ONE share handler. Every entry point calls this — the header icon and
   the Privacy-page block both land here. It can only ever send the public app
   link: no record, photo, vehicle, driver, PIN or company setting is reachable
   from it, and keeping that true is the point. */
function doShareApp(){
  var url=appShareUrl();
  if(navigator.share){
    navigator.share({title:APP_NAME,text:SHARE_APP_LINE,url:url})
      .catch(function(err){
        if(err&&err.name==='AbortError')return;   /* user backed out — say nothing */
        shareAppClipboard(url);                   /* anything else: fall through */
      });
    return;
  }
  shareAppClipboard(url);
}

function shareAppClipboard(url){
  var line=SHARE_APP_LINE+' '+url;
  if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(line).then(function(){toast('Link copied');})
      .catch(function(){shareAppFallback(line);});
  }else shareAppFallback(line);
}

/* clipboard refused (insecure context, permissions) — show the link instead of
   swallowing it, so there is always a way to get it out */
function shareAppFallback(line){
  showModal('<div class="stack"><h2>Share '+esc(APP_NAME)+'</h2>'+
    '<p class="muted">Copy this and send it on:</p>'+
    '<div class="card" style="word-break:break-all;font-size:13px;line-height:1.6">'+esc(line)+'</div>'+
    '<button class="btn" data-action="closeModal">Close</button></div>');
}

function toast(msg){
  var t=document.getElementById('toast');
  if(!t)return;
  t.textContent=msg;
  t.classList.add('show');
  clearTimeout(toast._t);
  toast._t=setTimeout(function(){t.classList.remove('show');},1900);
}

""" + A_CORE

# ------------------------------------------------------------------- the CSS
A_CSS = ".banner.show{display:block}"
R_CSS = """.banner.show{display:block}
#toast{position:fixed;left:50%;transform:translateX(-50%);bottom:calc(env(safe-area-inset-bottom) + 76px);
  z-index:60;background:var(--text);color:var(--surface);padding:10px 16px;border-radius:999px;
  font-size:14px;font-weight:600;opacity:0;pointer-events:none;transition:opacity .18s}
#toast.show{opacity:1}
.hbtn.share svg{width:20px;height:20px;display:block;margin:auto}
.sg{display:inline-flex;width:18px;height:18px}"""

# ------------------------------------------------------------- the toast node
A_NODE = '<div id="nudgeBanner" class="banner"></div>'
R_NODE = A_NODE + '\n<div id="toast" role="status" aria-live="polite"></div>'

# ------------------------------------------------------- header entry point
A_HEAD = ("""    (view.name==='home'?'<button class="hbtn" data-action="openMenu">☰</button>':'')+""")
R_HEAD = ("""    (view.name==='home'?'<button class="hbtn share" data-action="shareApp" aria-label="Share '+esc(APP_NAME)+'">'+EGS_SHARE_GLYPH+'</button>'+
      '<button class="hbtn" data-action="openMenu">☰</button>':'')+""")

# ------------------------------------------------ Privacy-page entry point
A_PRIV = ("""What you see is what you get. \U0001F341</p>'+
  '</div></main>');""")
R_PRIV = ("""What you see is what you get. \U0001F341</p>'+
  '</div>'+
  '<div class="card stack">'+
  '<h2>Share '+esc(APP_NAME)+'</h2>'+
  '<p class="muted">Passing it on is its own kind of support, and it costs nothing. This sends the app\\u2019s public link and nothing else \\u2014 none of your records, vehicles or drivers go with it.</p>'+
  '<button class="btn" data-action="shareApp" style="display:flex;align-items:center;justify-content:center;gap:8px"><span class="sg">'+EGS_SHARE_GLYPH+'</span> Share '+esc(APP_NAME)+'</button>'+
  '</div></main>');""")

# ----------------------------------------------------------------- the action
A_ACT = "  closeModal:hideModal,"
R_ACT = "  closeModal:hideModal,\n  shareApp:function(){doShareApp();},"

EDITS = [
    ("constants", A_CONST, R_CONST),
    ("core share block", A_CORE, R_CORE),
    ("toast + glyph CSS", A_CSS, R_CSS),
    ("toast node", A_NODE, R_NODE),
    ("header share icon", A_HEAD, R_HEAD),
    ("Privacy-page share block", A_PRIV, R_PRIV),
    ("shareApp action", A_ACT, R_ACT),
]


def die(msg):
    print("  ABORT: " + msg)
    sys.exit(1)


def main():
    if not HTML.exists():
        die("index.html not found — run this from the app folder")
    src = HTML.read_text(encoding="utf-8")

    if MARKER in src:
        print("  already applied (found the core share marker) — nothing to do")
        return

    stamp = time.strftime("%Y%m%d-%H%M%S")
    bak = HTML.with_suffix(HTML.suffix + f".bak.{stamp}")
    shutil.copy2(HTML, bak)
    print(f"== Backup ==\n  {bak}")

    print("== Edits ==")
    out = src
    for label, anchor, repl in EDITS:
        n = out.count(anchor)
        if n != 1:
            die(f"{label}: anchor matched {n} times, expected exactly 1\n"
                f"         anchor: {anchor[:90]!r}")
        out = out.replace(anchor, repl)
        print(f"  PASS  {label}")

    HTML.write_text(out, encoding="utf-8")

    # ---- validate --------------------------------------------------------
    print("== Validate ==")
    blocks = re.findall(r"<script[^>]*>(.*?)</script>", out, re.S)
    tmp = Path("/tmp/rw_fix02_check.js")
    tmp.write_text("\n;\n".join(b for b in blocks if b.strip()), encoding="utf-8")
    r = subprocess.run(["node", "--check", str(tmp)], capture_output=True, text=True)
    if r.returncode != 0:
        shutil.copy2(bak, HTML)
        die("inline JS failed node --check (index.html restored):\n" + r.stderr)
    print("  PASS  index.html inline JS parses")

    if out.count("onclick=") != 0:
        die("an inline onclick appeared — not allowed")
    print("  PASS  zero inline onclick")

    # both entry points must route through the one handler
    if out.count('data-action="shareApp"') != 2:
        die(f'expected exactly 2 shareApp entry points, found {out.count(chr(34)+"shareApp"+chr(34))}')
    print("  PASS  2 entry points, both data-action=\"shareApp\"")
    if out.count("function doShareApp(") != 1:
        die("expected exactly one doShareApp handler")
    print("  PASS  exactly one doShareApp() handler")

    print("\ndone — core share v2 in place")


if __name__ == "__main__":
    main()
