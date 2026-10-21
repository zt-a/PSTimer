#!/usr/bin/env bash
# Wait until the whole stack is up and healthy; on failure show the logs
# of the services that are not ready.
set -u

cd "$(dirname "$0")/.." || exit 1
timeout="${1:-120}"
deadline=$(( $(date +%s) + timeout ))

is_up() {
  name="$1"
  state=$(docker inspect --format '{{.State.Status}}' "$name" 2>/dev/null)
  health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$name" 2>/dev/null)
  [ "$state" = "running" ] || return 1
  case "$health" in
    healthy|none) return 0 ;;
    *) return 1 ;;
  esac
}

while [ "$(date +%s)" -lt "$deadline" ]; do
  ready=1
  for c in pstimer-db-1 pstimer-backend pstimer-frontend pstimer-worker; do
    is_up "$c" || ready=0
  done
  if [ "$ready" -eq 1 ]; then
    printf '\033[32mStack is up and healthy\033[0m\n'
    exit 0
  fi
  sleep 2
done

printf '\033[31mStack did not become healthy in %ss\033[0m\n' "$timeout" >&2
for c in pstimer-db-1 pstimer-backend pstimer-frontend pstimer-worker; do
  state=$(docker inspect --format '{{.State.Status}}' "$c" 2>/dev/null || echo "missing")
  health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}-{{end}}' "$c" 2>/dev/null || echo "-")
  printf '  %-18s state=%-12s health=%s\n' "$c" "$state" "$health"
done
printf '\n--- last logs ---\n'
docker compose logs --tail=25 2>&1 | tail -60
exit 1
