"""
Screenshot a page of the Svelte app start_web.sh serves, in the installed Chrome.

    python shoot_web.py OUT_DIR NAME ROUTE [--width 390] [--port 8599] [--session FILE]

ROUTE is the hash route, e.g. ours/month, ours/trend, mine, add, entries,
settings, home. The session (token + email) comes from start_web.sh's
session.json and is put in localStorage before the app loads, so it opens
logged in. Writes NAME.png (full page) and NAME_0.png, NAME_1.png... cut to
1400px each so they can be read. Needs playwright and pillow (see SKILL.md).
"""
import argparse
import json
import os
import tempfile
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("out_dir")
parser.add_argument("name")
parser.add_argument("route")
parser.add_argument("--width", type=int, default=1440)
parser.add_argument("--port", type=int, default=8599)
parser.add_argument("--session", default=os.path.join(os.environ.get("SHOT_DIR") or os.path.join(
    os.environ.get("TMPDIR") or tempfile.gettempdir(), "hf-shot"), "session.json"))
parser.add_argument("--logged-out", action="store_true", help="Open without a session (the login form).")
parser.add_argument("--dark", action="store_true", help="Shoot in dark mode (the app follows the device).")
args = parser.parse_args()

out = Path(args.out_dir)
out.mkdir(parents=True, exist_ok=True)
session = Path(args.session).read_text(encoding="utf-8").strip()
json.loads(session)  # fail early on a broken file

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    view = browser.new_page(viewport={"width": args.width, "height": 900},
                            color_scheme="dark" if args.dark else "light")
    if not args.logged_out:
        view.add_init_script(f"localStorage.setItem('hf-session', {json.dumps(session)})")
    errors = []
    view.on("pageerror", lambda e: errors.append(str(e)))
    view.on("console", lambda m: m.type == "error" and errors.append(m.text))
    view.goto(f"http://localhost:{args.port}/#/{args.route}", wait_until="networkidle", timeout=60000)
    time.sleep(2)  # let charts measure their width and draw
    view.screenshot(path=str(out / f"{args.name}.png"), full_page=True)
    browser.close()

image = Image.open(out / f"{args.name}.png").convert("RGB")
width, height = image.size
for i, top in enumerate(range(0, height, 1400)):
    image.crop((0, top, width, min(height, top + 1400))).save(out / f"{args.name}_{i}.png")
print(f"{out / args.name}.png: {(height + 1399) // 1400} part(s)")
for e in errors:
    print(f"browser error: {e}")
