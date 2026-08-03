#!/usr/bin/env python3
"""
Rollworthy — Fix 01: wire in the real icon set.

Run from the same folder as index.html:
    python3 fix_01_icons.py

The placeholder R icons are replaced by the real set. Three of the four
filenames are unchanged (icon-192, icon-512, icon-maskable-512), so the
manifest needs no edit at all — this script asserts that rather than
assuming it. The fourth changed name: icon-180.png -> apple-touch-icon.png,
which two places reference (the <link> tag and the service worker SHELL).

Also moves the two non-deployable brand files out of icons/ and into
brand/. icons/ must contain ONLY what the manifest and link tag name —
anything else is bulk that ships to phones for no reason.

Backs up first, applies edits with exact-match anchors, aborts atomically
if any anchor does not match exactly once, and validates JS before exiting.
"""
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HTML = Path("index.html")
SW = Path("service-worker.js")
MANIFEST = Path("manifest.webmanifest")
ICONS = Path("icons")
BRAND = Path("brand")
MARKER = "apple-touch-icon.png"  # already-applied guard

OLD_APPLE = "icon-180.png"
NEW_APPLE = "apple-touch-icon.png"

# (path, anchor, replacement)
EDITS = [
    (HTML,
     '<link rel="apple-touch-icon" href="icons/icon-180.png">',
     '<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">'),
    (SW,
     "  './icons/icon-maskable-512.png', './icons/icon-180.png'",
     "  './icons/icon-maskable-512.png', './icons/apple-touch-icon.png'"),
]

BRAND_FILES = ["rollworthy-master-1024.png", "legibility-preview.png"]


def die(msg):
    print("  ABORT: " + msg)
    sys.exit(1)


def main():
    stamp = time.strftime("%Y%m%d-%H%M%S")

    for p in (HTML, SW, MANIFEST):
        if not p.exists():
            die(f"{p} not found — run this from the app folder")

    # ---- already applied? ------------------------------------------------
    if MARKER in HTML.read_text(encoding="utf-8"):
        print("  already applied (found apple-touch-icon.png in index.html) — nothing to do")
        return

    # ---- the icon files must actually be on disk before we point at them --
    print("== Icon files ==")
    required = ["icon-192.png", "icon-512.png", "icon-maskable-512.png", NEW_APPLE]
    for name in required:
        f = ICONS / name
        if not f.exists():
            die(f"icons/{name} is missing — the new icon set is not in place")
        print(f"  PASS  icons/{name} present ({f.stat().st_size} bytes)")

    if (ICONS / OLD_APPLE).exists():
        die(f"icons/{OLD_APPLE} still exists — expected it to be replaced by {NEW_APPLE}")
    print(f"  PASS  icons/{OLD_APPLE} is gone (superseded by {NEW_APPLE})")

    # ---- verify the manifest needs NO edit, rather than assuming ----------
    print("== Manifest (verify only — no edit) ==")
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    want = {
        "icons/icon-192.png": ("192x192", None),
        "icons/icon-512.png": ("512x512", None),
        "icons/icon-maskable-512.png": ("512x512", "maskable"),
    }
    got = {i["src"]: (i.get("sizes"), i.get("purpose")) for i in m.get("icons", [])}
    if got != want:
        die(f"manifest icons do not match the shipped set.\n         want={want}\n         got ={got}")
    for src, (sizes, purpose) in want.items():
        if not (Path(".") / src).exists():
            die(f"manifest names {src} but it is not on disk")
        print(f"  PASS  {src}  {sizes}  purpose={purpose or 'any (default)'}")
    if m.get("start_url") != "./" or m.get("scope") != "./":
        die(f"start_url/scope must both be './' for the Pages subpath "
            f"(got {m.get('start_url')!r}/{m.get('scope')!r})")
    print("  PASS  start_url and scope are both './' (Pages subpath safe)")

    # ---- backup ----------------------------------------------------------
    print("== Backup ==")
    for p in (HTML, SW):
        b = p.with_suffix(p.suffix + f".bak.{stamp}")
        shutil.copy2(p, b)
        print(f"  {b}")

    # ---- apply edits, all-or-nothing -------------------------------------
    print("== Edits ==")
    staged = {}
    for path, anchor, repl in EDITS:
        src = staged.get(path, path.read_text(encoding="utf-8"))
        n = src.count(anchor)
        if n != 1:
            die(f"{path}: anchor matched {n} times, expected exactly 1\n         anchor: {anchor!r}")
        staged[path] = src.replace(anchor, repl)
        print(f"  PASS  {path}: {OLD_APPLE} -> {NEW_APPLE}")

    for path, text in staged.items():
        path.write_text(text, encoding="utf-8")

    # ---- move the non-deployable brand files out of icons/ ---------------
    print("== Brand files ==")
    BRAND.mkdir(exist_ok=True)
    for name in BRAND_FILES:
        src = ICONS / name
        if not src.exists():
            print(f"  SKIP  icons/{name} not present")
            continue
        shutil.move(str(src), str(BRAND / name))
        print(f"  PASS  icons/{name} -> brand/{name}")

    stray = sorted(p.name for p in ICONS.glob("*.png") if p.name not in required)
    if stray:
        die("icons/ still holds files the manifest does not name: " + ", ".join(stray))
    print("  PASS  icons/ holds exactly the 4 referenced files")

    # ---- validate --------------------------------------------------------
    print("== Validate ==")
    r = subprocess.run(["node", "--check", str(SW)], capture_output=True, text=True)
    if r.returncode != 0:
        die("service-worker.js failed node --check:\n" + r.stderr)
    print("  PASS  service-worker.js parses")

    blocks = re.findall(r"<script[^>]*>(.*?)</script>", HTML.read_text(encoding="utf-8"), re.S)
    tmp = Path("/tmp/rw_fix01_check.js")
    tmp.write_text("\n;\n".join(b for b in blocks if b.strip()), encoding="utf-8")
    r = subprocess.run(["node", "--check", str(tmp)], capture_output=True, text=True)
    if r.returncode != 0:
        die("index.html inline JS failed node --check:\n" + r.stderr)
    print("  PASS  index.html inline JS parses")

    # ---- the references now resolve to real files ------------------------
    html = HTML.read_text(encoding="utf-8")
    link = re.search(r'<link rel="apple-touch-icon" href="([^"]+)"', html)
    if not link or not Path(link.group(1)).exists():
        die("apple-touch-icon link does not resolve to a file on disk")
    print(f"  PASS  apple-touch-icon -> {link.group(1)} (exists)")

    sw = SW.read_text(encoding="utf-8")
    shell = re.search(r"const SHELL = \[(.*?)\]", sw, re.S).group(1)
    for asset in re.findall(r"'\./([^']+)'", shell):
        if asset and not Path(asset).exists():
            die(f"SHELL precaches ./{asset} but it is not on disk")
    print("  PASS  every SHELL asset exists on disk")

    print("\ndone — icons wired in")


if __name__ == "__main__":
    main()
