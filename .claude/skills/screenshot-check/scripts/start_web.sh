#!/usr/bin/env bash
# Serve a build of the Svelte app (web/) for screenshots, without touching the real app.
#
#   bash .claude/skills/screenshot-check/scripts/start_web.sh [port]     (default 8599)
#
# Builds web/ and runs `vite preview` on PORT, forwarding /api to the API on
# localhost:8000 (the running backend container, so the shots show real data).
# Mints a token for $SHOT_EMAIL (default: the first account) in the backend
# container and writes it to $SHOT_DIR/session.json, which shoot_web.py puts
# in the page's localStorage so the app opens logged in. Stop it with stop.sh.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
PORT="${1:-8599}"
SHOT_DIR="${SHOT_DIR:-${TMPDIR:-/tmp}/hf-shot}"

bash .claude/skills/screenshot-check/scripts/stop.sh "$PORT" >/dev/null 2>&1 || true
mkdir -p "$SHOT_DIR"

EMAIL="${SHOT_EMAIL:-$(docker exec -i personal_finance_api python -c "import database, models; s = database.SessionLocal(); print(s.query(models.DimUser).order_by(models.DimUser.user_id).first().email)" | tail -1)}"
TOKEN="$(docker exec -i personal_finance_api python -c "import auth; print(auth.create_access_token({'sub': '$EMAIL'}))" | tail -1)"
printf '{"token": "%s", "email": "%s", "renewedAt": %s000}\n' "$TOKEN" "$EMAIL" "$(date +%s)" > "$SHOT_DIR/session.json"

cd web
[ -d node_modules ] || npm ci --no-audit --no-fund
npm run build > "$SHOT_DIR/build.log" 2>&1
nohup npx vite preview --port "$PORT" --strictPort > "$SHOT_DIR/preview.log" 2>&1 &
for _ in $(seq 1 30); do
  curl -s -o /dev/null http://localhost:"$PORT"/ && break
  sleep 1
done
echo "running: http://localhost:$PORT/ (as $EMAIL; session in $SHOT_DIR/session.json)"
