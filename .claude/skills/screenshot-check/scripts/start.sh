#!/usr/bin/env bash
# Run a logged-in copy of the frontend for screenshots, without touching the real app.
#
#   bash .claude/skills/screenshot-check/scripts/start.sh [port]     (default 8599)
#
# Copies frontend/ (no .venv, no tests) to $SHOT_DIR (default: a temp folder),
# adds an entry page that logs in with a token minted in the backend container
# (the running container personal_finance_api, so it works from a git worktree too)
# for $SHOT_EMAIL (default: the first account) and opens ?page=..., then runs it
# with the frontend's own venv against the API on localhost:8000. Prints the
# URL and leaves it running; stop it with stop.sh. Re-run after editing a
# module: Streamlit keeps imported modules until it restarts.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
PORT="${1:-8599}"
SHOT_DIR="${SHOT_DIR:-${TMPDIR:-/tmp}/hf-shot}"

bash .claude/skills/screenshot-check/scripts/stop.sh >/dev/null 2>&1 || true
rm -rf "$SHOT_DIR" && mkdir -p "$SHOT_DIR"
(cd frontend && cp -r pages sections assets .streamlit ./*.py "$SHOT_DIR/")  # *.py has Home.py

cat > "$SHOT_DIR/Shot.py" <<'PY'
"""Screenshot entry: logs in with a minted token, then opens the page named in ?page=."""
import os
import streamlit as st

st.session_state["access_token"] = os.environ["SHOT_TOKEN"]
st.session_state["user_email"] = os.environ.get("SHOT_EMAIL", "")
st.switch_page(st.query_params.get("page", "pages/2_Our_expenses.py"))
PY

EMAIL="${SHOT_EMAIL:-$(docker exec -i personal_finance_api python -c "import database, models; s = database.SessionLocal(); print(s.query(models.DimUser).order_by(models.DimUser.user_id).first().email)" | tail -1)}"
TOKEN="$(docker exec -i personal_finance_api python -c "import auth; print(auth.create_access_token({'sub': '$EMAIL'}))" | tail -1)"

# The frontend's own venv; SHOT_PYTHON overrides it (a git worktree has no .venv of its own).
if [ -n "${SHOT_PYTHON:-}" ]; then
  PYTHON="$SHOT_PYTHON"
else
  PYTHON=frontend/.venv/Scripts/python.exe
  [ -x "$PYTHON" ] || PYTHON=frontend/.venv/bin/python
  PYTHON="$(cd "$(dirname "$PYTHON")" && pwd)/$(basename "$PYTHON")"
fi

cd "$SHOT_DIR"
SHOT_TOKEN="$TOKEN" SHOT_EMAIL="$EMAIL" API_URL=http://localhost:8000 nohup "$PYTHON" -m streamlit run Shot.py \
  --server.port "$PORT" --server.headless true --browser.gatherUsageStats false > streamlit.log 2>&1 &
echo $! > "$SHOT_DIR/streamlit.pid"
for _ in $(seq 1 30); do
  curl -s -o /dev/null http://localhost:"$PORT"/ && break
  sleep 1
done
echo "running: http://localhost:$PORT/?page=pages/2_Our_expenses.py (as $EMAIL)"
