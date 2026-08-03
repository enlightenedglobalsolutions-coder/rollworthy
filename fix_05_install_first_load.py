#!/usr/bin/env python3
"""
Rollworthy — Fix 05: show the install banner on first load.

Run from the same folder as index.html:
    python3 fix_05_install_first_load.py

The original complaint was "no install prompt on FIRST load". Fix 03 gated the
banner behind `if(!cfg)return;` — copied from Notebuilt, whose gate gaurds a PIN
lock screen. Rollworthy's equivalent is a setup wizard, which is not a security
boundary, so the gate was wrong here.

TWO THINGS SUPPRESSED IT, NOT ONE
Removing the !cfg line alone would have changed nothing: render() returns early
in its own `if(!cfg)` branch, before maybeShowInstall() is ever reached. So this
also calls it from that branch — from the first-run LANDING screen only.

Net behaviour, on which SHOWS the banner:
    no cfg + first-run landing  -> shown   (the case that was reported)
    no cfg + setup wizard       -> never raises it
    cfg    + home               -> shown
    cfg    + anywhere else      -> never raises it

NOTE, verified in-browser: these control where the banner is RAISED, not where
it is visible. The banner is a persistent fixed element, like the update and
backup banners — once raised on the landing screen it stays up across
navigation, including onto the setup wizard, until dismissed or installed. It
sits below the form and does not obstruct it. Hiding it per-screen would mean
tracking show/hide state across every render; not worth it for a banner the
user can dismiss with one tap.

Backs up first, exact-match anchors, ==1 guard, atomic, node --check.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HTML = Path("index.html")
MARKER = "/* first-run landing counts as home for the install banner */"

# 1. the guard: drop the cfg requirement, keep the screen requirement
A_GUARD = """  if(view.name!=='home')return;              /* never mid-inspection */
  if(!cfg)return;                            /* not through first-run setup yet */"""
R_GUARD = """  /* first-run landing counts as home for the install banner */
  if(cfg&&view.name!=='home')return;         /* never mid-inspection */"""

# 2. render() returns early when there is no cfg — reach the banner from there,
#    but only on the landing screen, never over the setup wizard.
A_RENDER = """  if(!cfg){
    if(view.name==='setup')renderSetup();
    else renderFirstRun();
    return;
  }"""
R_RENDER = """  if(!cfg){
    if(view.name==='setup'){renderSetup();return;}   /* no banner over the wizard */
    renderFirstRun();
    maybeShowInstall();
    return;
  }"""

EDITS = [
    ("install guard drops the cfg requirement", A_GUARD, R_GUARD),
    ("first-run branch reaches maybeShowInstall", A_RENDER, R_RENDER),
]


def die(msg):
    print("  ABORT: " + msg)
    sys.exit(1)


def main():
    if not HTML.exists():
        die("index.html not found — run this from the app folder")
    src = HTML.read_text(encoding="utf-8")

    if MARKER in src:
        print("  already applied — nothing to do")
        return
    if "ft_installDismissed" not in src:
        die("fix_03_install_prompt.py has not been applied — run it first")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    bak = HTML.with_suffix(HTML.suffix + f".bak.{stamp}")
    shutil.copy2(HTML, bak)
    print(f"== Backup ==\n  {bak}")

    print("== Edits ==")
    out = src
    for label, anchor, repl in EDITS:
        n = out.count(anchor)
        if n != 1:
            die(f"{label}: anchor matched {n} times, expected exactly 1")
        out = out.replace(anchor, repl)
        print(f"  PASS  {label}")

    HTML.write_text(out, encoding="utf-8")

    # ---- validate --------------------------------------------------------
    print("== Validate ==")
    blocks = re.findall(r"<script[^>]*>(.*?)</script>", out, re.S)
    tmp = Path("/tmp/rw_fix05_check.js")
    tmp.write_text("\n;\n".join(b for b in blocks if b.strip()), encoding="utf-8")
    r = subprocess.run(["node", "--check", str(tmp)], capture_output=True, text=True)
    if r.returncode != 0:
        shutil.copy2(bak, HTML)
        die("inline JS failed node --check (index.html restored):\n" + r.stderr)
    print("  PASS  index.html inline JS parses")

    if "if(!cfg)return;" in out:
        die("the cfg gate is still present in maybeShowInstall")
    print("  PASS  cfg gate removed")
    # three call sites: the beforeinstallprompt handler, the render tail, and
    # the new first-run landing branch
    if out.count("maybeShowInstall();") != 3:
        die(f"expected 3 maybeShowInstall() call sites (beforeinstallprompt + "
            f"render tail + first-run), found {out.count('maybeShowInstall();')}")
    print("  PASS  3 call sites: beforeinstallprompt, render tail, first-run landing")
    if "if(view.name==='setup'){renderSetup();return;}" not in out:
        die("the setup wizard is no longer excluded")
    print("  PASS  setup wizard still excluded")

    print("\ndone — install banner now shows on first load")


if __name__ == "__main__":
    main()
