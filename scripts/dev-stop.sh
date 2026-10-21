#!/usr/bin/env bash
# Stop the local dev servers (uvicorn backend / vite frontend) so that the
# Docker stack can bind its ports (80 and 8000).
#
# Only processes of THIS project are touched.
set -u

stopped=0

stop_pattern() {
  pattern="$1"; label="$2"
  pids=$(pgrep -f "$pattern" 2>/dev/null | tr '\n' ' ')
  [ -z "$pids" ] && return 0
  echo "stopping $label (pid: $pids)"
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null
  sleep 1
  # shellcheck disable=SC2086
  pids=$(pgrep -f "$pattern" 2>/dev/null | tr '\n' ' ')
  # shellcheck disable=SC2086
  [ -n "$pids" ] && kill -9 $pids 2>/dev/null
  stopped=1
}

# The bracket keeps pgrep from matching this script itself.
stop_pattern "[u]vicorn app.main:app" "local backend (uvicorn)"
stop_pattern "[n]ode .*vite" "local frontend (vite)"

if [ "$stopped" -eq 0 ]; then
  echo "no local dev servers running"
else
  echo "local dev servers stopped — ports 80/8000 are free for Docker"
fi
