"""
Screenshot a page of the copy start.sh runs, in the installed Chrome.

    python shoot.py OUT_DIR NAME PAGE [--tab "Month by month"] [--width 390] [--port 8599]

PAGE is a path like pages/2_Our_expenses.py. Writes NAME.png (the whole
page: the viewport is tall, because Streamlit scrolls inside its own
container and a "full page" capture only gets the first screen) and
NAME_0.png, NAME_1.png... cut to 1400px each so they can be read.
Needs playwright and pillow (see SKILL.md), not the project's own venv.
"""
import argparse
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("out_dir")
parser.add_argument("name")
parser.add_argument("page")
parser.add_argument("--tab")
parser.add_argument("--width", type=int, default=1440)
parser.add_argument("--port", type=int, default=8599)
parser.add_argument("--height", type=int, default=6500)
args = parser.parse_args()

out = Path(args.out_dir)
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    view = browser.new_page(viewport={"width": args.width, "height": args.height})
    view.goto(f"http://localhost:{args.port}/?page={args.page}", wait_until="networkidle", timeout=60000)
    view.wait_for_selector("[data-testid='stMainBlockContainer']", timeout=60000)
    time.sleep(6)  # charts draw a moment after the network settles
    if args.tab:
        view.get_by_role("tab", name=args.tab).click()
        time.sleep(5)
    view.screenshot(path=str(out / f"{args.name}.png"))
    browser.close()

# Cut off the empty page background below the content, then into readable parts.
image = Image.open(out / f"{args.name}.png").convert("RGB")
width, height = image.size
pixels = image.load()
background = pixels[width - 5, height - 5]
bottom = height
while bottom > 1 and all(pixels[x, bottom - 1] == background for x in range(width // 4, width - 5, 25)):
    bottom -= 1
for i, top in enumerate(range(0, max(bottom, 1), 1400)):
    image.crop((0, top, width, min(bottom, top + 1400))).save(out / f"{args.name}_{i}.png")
print(f"{out / args.name}.png: {(bottom + 1399) // 1400} part(s)")
