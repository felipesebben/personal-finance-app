#!/usr/bin/env bash
# Stop the screenshot copy started by start.sh: whatever listens on its port (default 8599).
PORT="${1:-8599}"
if command -v taskkill >/dev/null 2>&1; then  # Windows (Git Bash): the python process is a Windows one
  for pid in $(netstat -ano | grep -E "[:.]$PORT[[:space:]].*LISTENING" | awk '{print $NF}' | sort -u); do
    taskkill //F //T //PID "$pid" >/dev/null 2>&1 && echo "stopped $pid"
  done
else
  pids="$(lsof -ti tcp:"$PORT" 2>/dev/null || true)"
  [ -n "$pids" ] && kill $pids && echo "stopped $pids"
fi
exit 0
