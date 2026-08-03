#!/usr/bin/env python3
"""
Rollworthy — Fix 06: version stamp on the first-run screen.

Run from the same folder as index.html:
    python3 fix_06_firstrun_version.py

WHY
Fix 04 put a visible version stamp in two places: the home footer and Manager.
Both require a company to exist — Manager also requires the PIN. The first-run
screen has neither a header nor a footer, so a fresh visitor (which is what
every incognito window and every new phone is) sees NO version anywhere.

That was found the hard way: a deploy landed correctly on origin, Pages built
green, and every edge served the new build — but checking it in incognito showed
a screen with no version on it, which is indistinguishable from a failed deploy.
The chain was fine; the ability to confirm it was missing. A version stamp you
cannot reach before setup does not do the job it exists to do.

This adds the same stamp, reading the same single source (window.EGS_VERSION),
to the first-run screen.

Backs up first, exact-match anchor, ==1 guard, atomic, node --check.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HTML = Path("index.html")
MARKER = 'id="firstrun-version"'

A_FIRSTRUN = """      '<p class="muted center">Managers set up a new company. Drivers import the setup file their manager shares with them.</p>'+
    '</div>'+
  '</main>');"""
R_FIRSTRUN = """      '<p class="muted center">Managers set up a new company. Drivers import the setup file their manager shares with them.</p>'+
    '</div>'+
    /* the only screen a fresh visitor sees — without this there is no way to
       tell which build is running until a company exists */
    '<footer class="egs" id="firstrun-version">'+esc(APP_NAME)+' \\u00b7 EGS \\u00b7 v'+esc(window.EGS_VERSION)+'</footer>'+
  '</main>');"""


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

    stamp = time.strftime("%Y%m%d-%H%M%S")
    bak = HTML.with_suffix(HTML.suffix + f".bak.{stamp}")
    shutil.copy2(HTML, bak)
    print(f"== Backup ==\n  {bak}")

    print("== Edits ==")
    n = src.count(A_FIRSTRUN)
    if n != 1:
        die(f"first-run render: anchor matched {n} times, expected exactly 1")
    out = src.replace(A_FIRSTRUN, R_FIRSTRUN)
    print("  PASS  version stamp added to the first-run screen")

    HTML.write_text(out, encoding="utf-8")

    # ---- validate --------------------------------------------------------
    print("== Validate ==")
    blocks = re.findall(r"<script[^>]*>(.*?)</script>", out, re.S)
    tmp = Path("/tmp/rw_fix06_check.js")
    tmp.write_text("\n;\n".join(b for b in blocks if b.strip()), encoding="utf-8")
    r = subprocess.run(["node", "--check", str(tmp)], capture_output=True, text=True)
    if r.returncode != 0:
        shutil.copy2(bak, HTML)
        die("inline JS failed node --check (index.html restored):\n" + r.stderr)
    print("  PASS  index.html inline JS parses")

    # three stamps now, all reading the one source of truth
    if out.count("esc(window.EGS_VERSION)") != 3:
        die(f"expected 3 version stamps reading window.EGS_VERSION, "
            f"found {out.count('esc(window.EGS_VERSION)')}")
    print("  PASS  3 stamps (first-run, home footer, Manager), one source")

    # the whole point: reachable with no company set up
    fr = re.search(r"function renderFirstRun\(\)\{[\s\S]*?\n\}", out)
    if not fr or "window.EGS_VERSION" not in fr.group(0):
        die("renderFirstRun does not render the version — the gap is not closed")
    print("  PASS  reachable before any company exists")

    print("\ndone — version visible on first run")


if __name__ == "__main__":
    main()
