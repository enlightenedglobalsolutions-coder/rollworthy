#!/usr/bin/env python3
"""
Rollworthy — Fix 03: the install prompt.

Run from the same folder as index.html:
    python3 fix_03_install_prompt.py

WHY THIS EXISTS
The manifest was never the problem. start_url/scope are './', every path is
relative, the SW controls the page, and Chrome's install criteria all pass —
the app IS installable. Chrome simply stopped showing the automatic
mini-infobar in Chrome 76, so an installable PWA that never listens for
beforeinstallprompt offers the user nothing. Rollworthy had zero install
handling. A clean manifest ships no fix; this does.

THE STORAGE KEY IS PREFIXED, DELIBERATELY
Notebuilt writes the BARE key 'installPromptDismissed' (its lines 3894/3970).
Every EGS app shares one github.io origin, so a bare key is a cross-app
collision — that is exactly what silenced Kept's banner (DECISIONS 2026-08-01,
"audit any other app that writes the bare key"). This uses ft_installDismissed.
Notebuilt is still bare and wants the same repair.

iOS
iOS and iPadOS Safari never fire beforeinstallprompt, so without a second path
the banner would silently never appear there. navigator.standalone is a
WebKit-only property, so testing for its presence is a feature test for that
family — no user-agent string parsing, which lies (iPadOS reports as Mac).

ONE BANNER AT A TIME
The update banner, the backup nudge and this all own the same slot at the
bottom of the screen. Install always yields to the other two: an update the
user hasn't taken, or records they haven't backed up, both matter more than an
install nudge. maybeNudge() yields back, so the two can never stack.

Backs up first, exact-match anchors, ==1 guard, atomic, node --check.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HTML = Path("index.html")
MARKER = "ft_installDismissed"  # already-applied guard

# ------------------------------------------------------------ the storage key
A_KEY = ("var LS_CFG='ft_cfg', LS_REC='ft_records', LS_RES='ft_res', "
         "LS_DRIVER='ft_driver', LS_NUDGE='ft_nudge';")
R_KEY = ("var LS_CFG='ft_cfg', LS_REC='ft_records', LS_RES='ft_res', "
         "LS_DRIVER='ft_driver', LS_NUDGE='ft_nudge',\n"
         "    LS_INSTALL='ft_installDismissed';\n"
         "/* Every key above is ft_-prefixed on purpose. All EGS apps share one\n"
         "   origin, so a bare key is a cross-app collision — that is what silenced\n"
         "   Kept's install banner (DECISIONS 2026-08-01). */")

# -------------------------------------------------------------- the banner node
A_NODE = '<div id="toast" role="status" aria-live="polite"></div>'
R_NODE = '<div id="installBanner" class="banner"></div>\n' + A_NODE

# ------------------------------------------------------------------- the logic
A_LOGIC = """function maybeNudge(){
  if(view.name!=='home')return;"""
R_LOGIC = """/* ---------- install prompt ---------- */
var deferredInstall=null, installShown=false;

/* iOS/iPadOS Safari never fires beforeinstallprompt. navigator.standalone is a
   WebKit-only property, so its presence is a feature test for that family —
   not user-agent sniffing, which lies (iPadOS reports itself as a Mac). */
function isIOSSafari(){return 'standalone' in navigator;}
function isInstalled(){
  return window.matchMedia('(display-mode: standalone)').matches || navigator.standalone===true;
}
/* One banner at a time. Install always yields to the update banner and the
   backup nudge — both matter more than an install suggestion. */
function bannerBusy(){
  var u=document.getElementById('updateBanner'), n=document.getElementById('nudgeBanner');
  return !!((u&&u.classList.contains('show'))||(n&&n.classList.contains('show')));
}
function maybeShowInstall(){
  if(installShown)return;
  if(view.name!=='home')return;              /* never mid-inspection */
  if(!cfg)return;                            /* not through first-run setup yet */
  if(isInstalled())return;                   /* already on the home screen */
  if(localStorage.getItem(LS_INSTALL))return;/* dismissed before */
  if(bannerBusy())return;
  if(!deferredInstall&&!isIOSSafari())return;/* nothing to offer on this browser */
  showInstallBanner(deferredInstall?'prompt':'ios');
}
function showInstallBanner(mode){
  installShown=true;
  var b=document.getElementById('installBanner');
  if(!b)return;
  b.innerHTML='<div class="row between"><div><strong>Add '+esc(APP_NAME)+' to your home screen</strong>'+
    '<div class="muted">'+(mode==='prompt'
      ? 'Opens full screen and works with no signal.'
      : 'Tap Share, then \\u201cAdd to Home Screen\\u201d.')+'</div></div>'+
    '<div class="row">'+
      (mode==='prompt'?'<button class="btn small primary" data-action="installGo">Add</button>':'')+
      '<button class="btn small" data-action="installDismiss">Not now</button>'+
    '</div></div>';
  b.classList.add('show');
}
function hideInstallBanner(){
  var b=document.getElementById('installBanner');
  if(b)b.classList.remove('show');
}
window.addEventListener('beforeinstallprompt',function(e){
  e.preventDefault();          /* keep Chrome's own UI out of the way */
  deferredInstall=e;
  maybeShowInstall();
});
window.addEventListener('appinstalled',function(){
  localStorage.setItem(LS_INSTALL,'1');
  hideInstallBanner();
});

function maybeNudge(){
  if(view.name!=='home')return;
  var ib=document.getElementById('installBanner');
  if(ib&&ib.classList.contains('show'))return;   /* never stack on the install banner */"""

# ------------------------------------------------------------- the render hook
A_CALL = """  maybeNudge();
}"""
R_CALL = """  maybeShowInstall();
  maybeNudge();
}"""

# ---------------------------------------------------------------- the actions
A_ACT = "  shareApp:function(){doShareApp();},"
R_ACT = """  shareApp:function(){doShareApp();},
  installGo:function(){
    if(!deferredInstall){hideInstallBanner();return;}
    deferredInstall.prompt();
    deferredInstall.userChoice.then(function(){deferredInstall=null;hideInstallBanner();});
  },
  installDismiss:function(){localStorage.setItem(LS_INSTALL,'1');hideInstallBanner();},"""

EDITS = [
    ("prefixed storage key", A_KEY, R_KEY),
    ("install banner node", A_NODE, R_NODE),
    ("install logic + nudge mutual exclusion", A_LOGIC, R_LOGIC),
    ("render hook", A_CALL, R_CALL),
    ("installGo / installDismiss actions", A_ACT, R_ACT),
]


def die(msg):
    print("  ABORT: " + msg)
    sys.exit(1)


def main():
    if not HTML.exists():
        die("index.html not found — run this from the app folder")
    src = HTML.read_text(encoding="utf-8")

    if MARKER in src:
        print("  already applied (found ft_installDismissed) — nothing to do")
        return
    if "EGS CORE — SHARE · v2" not in src:
        die("fix_02_share_core_v2.py has not been applied — run it first")

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
    tmp = Path("/tmp/rw_fix03_check.js")
    tmp.write_text("\n;\n".join(b for b in blocks if b.strip()), encoding="utf-8")
    r = subprocess.run(["node", "--check", str(tmp)], capture_output=True, text=True)
    if r.returncode != 0:
        shutil.copy2(bak, HTML)
        die("inline JS failed node --check (index.html restored):\n" + r.stderr)
    print("  PASS  index.html inline JS parses")

    if out.count("onclick=") != 0:
        die("an inline onclick appeared — not allowed")
    print("  PASS  zero inline onclick")

    if "localStorage.getItem('installPromptDismissed')" in out or \
       "localStorage.setItem('installPromptDismissed'" in out:
        die("a BARE installPromptDismissed key is present — must be ft_-prefixed")
    print("  PASS  no bare installPromptDismissed key (shared-origin safe)")

    for needed in ("beforeinstallprompt", "appinstalled", "isIOSSafari", "bannerBusy"):
        if needed not in out:
            die(f"expected {needed} in the applied source")
    print("  PASS  beforeinstallprompt + appinstalled + iOS path + mutual exclusion present")

    print("\ndone — install prompt in place")


if __name__ == "__main__":
    main()
