---
name: screenshot-check
description: Look at a Home Finances page the way a person sees it — a logged-in build of the web app on its own port, screenshot in the installed Chrome at desktop and phone width — before handing UI work over. Use after any change to web/ pages, sections, ui components or charts, and whenever a layout question can't be settled from code or unit tests.
---

# Screenshot check

AppTest has no pixels and a chart's PNG render has no page around it. Squeezed charts, a card taller than its content, a chart that silently doesn't draw, a label cut off on a phone: those only show in a real browser. This skill is how to look, without touching the app Felipe is using.

## One-time setup

Playwright drives the Chrome already installed (`channel="chrome"`), so it downloads no browser. It needs a venv at a **short path**: Playwright's own files overflow Windows' path limit inside a deep folder like the session scratchpad.

```bash
python -m venv "$LOCALAPPDATA/Temp/pwv"
"$LOCALAPPDATA/Temp/pwv/Scripts/python.exe" -m pip install playwright pillow
```

Check: `"$LOCALAPPDATA/Temp/pwv/Scripts/python.exe" -c "import playwright.sync_api, PIL; print('ok')"` prints `ok`.

## Each time (the Svelte app, web/)

1. **Start a build** (the backend and db must be up): `bash .claude/skills/screenshot-check/scripts/start_web.sh` (port 8599). It builds `web/`, serves it with `vite preview` forwarding `/api` to the API on localhost:8000 (real data), and mints a token for the first account (`SHOT_EMAIL=...` to pick another) into `$SHOT_DIR/session.json`. Expected last line: `running: http://localhost:8599/ ...`. Re-run it after editing `web/`: it serves a build, not the sources.

2. **Shoot** each page and tab you changed, at desktop and phone width (the route is the URL hash):

   ```bash
   PW="$LOCALAPPDATA/Temp/pwv/Scripts/python.exe"
   OUT=<the session scratchpad>/shots
   "$PW" .claude/skills/screenshot-check/scripts/shoot_web.py "$OUT" our_month ours/month
   "$PW" .claude/skills/screenshot-check/scripts/shoot_web.py "$OUT" our_trend_phone ours/trend --width 390
   "$PW" .claude/skills/screenshot-check/scripts/shoot_web.py "$OUT" login home --logged-out
   ```

   Each writes `NAME.png` (full page) and parts `NAME_0.png`... of 1400px, and prints any browser error (`browser error: ...`), which means a page broke. On a phone-width shot the fixed bottom tab bar is drawn once, part-way down the full-page capture: that's the capture, not the layout.

3. **Read the parts** and check them as below. 4. **Stop:** `bash .claude/skills/screenshot-check/scripts/stop.sh`.

## Each time (the legacy Streamlit app, frontend/)

1. **Start the copy** (the backend and db must be up):

   ```bash
   bash .claude/skills/screenshot-check/scripts/start.sh        # port 8599
   ```

   It copies `frontend/` to a temp folder and logs in as the first account (`SHOT_EMAIL=... ` to pick another) with a token minted in the backend container. It then runs the copy on port 8599 against the real API, so the screenshots show the real data. Expected last line: `running: http://localhost:8599/...`. Re-run it after editing a module: Streamlit keeps imported modules until it restarts.

2. **Shoot** each page, and each tab you changed, at desktop and phone width:

   ```bash
   PW="$LOCALAPPDATA/Temp/pwv/Scripts/python.exe"
   OUT=<the session scratchpad>/shots
   "$PW" .claude/skills/screenshot-check/scripts/shoot.py "$OUT" our_month pages/2_Our_expenses.py
   "$PW" .claude/skills/screenshot-check/scripts/shoot.py "$OUT" our_mbm pages/2_Our_expenses.py --tab "Month by month"
   "$PW" .claude/skills/screenshot-check/scripts/shoot.py "$OUT" our_phone pages/2_Our_expenses.py --width 390
   ```

   Each writes `NAME.png` and readable parts `NAME_0.png`, `NAME_1.png`... (1400px each). The viewport is 6500px tall on purpose: Streamlit scrolls inside its own container, so a "full page" capture would only get the first screen.

3. **Read the parts** (the Read tool shows images) and check them against the gestalt-review skill. Look in particular for:
   - charts that didn't draw;
   - rows squeezed together or labels hidden;
   - values cut off at a bar's tip, above all on the phone;
   - cards in a row with different heights, or empty bands inside a card;
   - text pressed against the chart under it;
   - a control row that wraps.

4. **Stop the copy:** `bash .claude/skills/screenshot-check/scripts/stop.sh`.

## To act on a page (tap a pill, tick a row)

Write a short Playwright script in the scratchpad, on the pattern of `shoot.py`: open the page, `view.locator(...).click()`, wait, screenshot. Never press Save or Delete. The copy runs against the real API and the real data.

## Limits

- It shows one account's data. A view that's empty for it, such as a card that only appears with history, still needs an AppTest with fake data.
- Felipe's laptop and phone are the final check.
