#!/usr/bin/env python3
"""
Rollworthy — Fix 04: visible version stamp in Manager.

Run from the same folder as index.html:
    python3 fix_04_version_stamp.py

Notebuilt puts the running version at the bottom of Settings so you can
eyeball running-vs-deployed without opening devtools. Rollworthy has no
Settings page; Manager is its analogue, and it is where a manager already
goes to check company setup. The home footer already carries a stamp — this
adds the second one where the equivalent Notebuilt check lives, so a manager
can confirm an update landed from inside the tool they actually use.

Backs up first, exact-match anchor, ==1 guard, atomic, node --check.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HTML = Path("index.html")
MARKER = "mgr-version"  # already-applied guard

A_MGR = ("  h(header('Manager', cfg.company, 'goHome')+'<main><div class=\"tabs\">'"
         "+tabs+'</div>'+body+'</main>');")
R_MGR = ("  h(header('Manager', cfg.company, 'goHome')+'<main><div class=\"tabs\">'+tabs+'</div>'+body+\n"
         "    '<footer class=\"egs\" id=\"mgr-version\">'+esc(APP_NAME)+' \\u00b7 EGS \\u00b7 v'+esc(window.EGS_VERSION)+\n"
         "    '<br>This is the version running on this phone.</footer>'+\n"
         "  '</main>');")


def die(msg):
    print("  ABORT: " + msg)
    sys.exit(1)


def main():
    if not HTML.exists():
        die("index.html not found — run this from the app folder")
    src = HTML.read_text(encoding="utf-8")

    if MARKER in src:
        print("  already applied (found mgr-version) — nothing to do")
        return

    stamp = time.strftime("%Y%m%d-%H%M%S")
    bak = HTML.with_suffix(HTML.suffix + f".bak.{stamp}")
    shutil.copy2(HTML, bak)
    print(f"== Backup ==\n  {bak}")

    print("== Edits ==")
    n = src.count(A_MGR)
    if n != 1:
        die(f"Manager render: anchor matched {n} times, expected exactly 1")
    out = src.replace(A_MGR, R_MGR)
    print("  PASS  version stamp appended to Manager")

    HTML.write_text(out, encoding="utf-8")

    # ---- validate --------------------------------------------------------
    print("== Validate ==")
    blocks = re.findall(r"<script[^>]*>(.*?)</script>", out, re.S)
    tmp = Path("/tmp/rw_fix04_check.js")
    tmp.write_text("\n;\n".join(b for b in blocks if b.strip()), encoding="utf-8")
    r = subprocess.run(["node", "--check", str(tmp)], capture_output=True, text=True)
    if r.returncode != 0:
        shutil.copy2(bak, HTML)
        die("inline JS failed node --check (index.html restored):\n" + r.stderr)
    print("  PASS  index.html inline JS parses")

    # both stamps must read the same single source of truth
    if out.count("esc(window.EGS_VERSION)") != 2:
        die(f"expected exactly 2 version stamps reading window.EGS_VERSION, "
            f"found {out.count('esc(window.EGS_VERSION)')}")
    print("  PASS  2 stamps (home footer + Manager), both from window.EGS_VERSION")

    print("\ndone — version stamp visible in Manager")


if __name__ == "__main__":
    main()
