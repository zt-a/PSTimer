#!/usr/bin/env bash
# Pre-flight check for the Docker deployment.
# Usage: bash scripts/doctor.sh   (or: make doctor)
set -u

fail=0
ok()   { printf '  \033[32mOK\033[0m    %s\n' "$1"; }
warn() { printf '  \033[33mWARN\033[0m  %s\n' "$1"; }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; fail=1; }

cd "$(dirname "$0")/.." || exit 1

echo "==> Docker"
if ! command -v docker >/dev/null 2>&1; then
  bad "docker not found — install Docker Engine 20.10+"
elif ! docker info >/dev/null 2>&1; then
  bad "cannot talk to the Docker daemon — is it running? Are you in the 'docker' group?"
  bad "  fix: sudo systemctl start docker && sudo usermod -aG docker \$USER (then re-login)"
else
  ok "docker daemon is reachable ($(docker version --format '{{.Server.Version}}' 2>/dev/null))"
fi

echo "==> Compose"
if docker compose version >/dev/null 2>&1; then
  ver=$(docker compose version --short 2>/dev/null)
  ok "docker compose v2 present ($ver)"
  major=${ver%%.*}
  if [ "$major" -lt 2 ] 2>/dev/null; then
    bad "compose v2 required (found $ver) — 'docker compose up' is not supported"
  fi
elif command -v docker-compose >/dev/null 2>&1; then
  bad "only legacy docker-compose v1 found — install the Compose v2 plugin"
  bad "  fix: sudo apt-get install docker-compose-plugin"
else
  bad "docker compose not found — install the Compose v2 plugin"
fi

echo "==> Compose file"
if docker compose config >/dev/null 2>&1; then
  ok "docker-compose.yml is valid"
else
  bad "docker-compose.yml is invalid:"
  docker compose config 2>&1 | tail -5 | sed 's/^/        /'
fi

echo "==> Ports"
check_port() {
  port="$1"; label="$2"
  line=$(ss -ltnp 2>/dev/null | awk -v p=":$port\$" '$4 ~ p {print; exit}')
  if [ -z "$line" ]; then
    ok "port $port ($label) is free"
    return
  fi
  if docker ps --format '{{.Names}} {{.Ports}}' 2>/dev/null | grep -q ":$port->"; then
    ok "port $port ($label) is used by our own container (stack already running)"
    return
  fi
  who=$(printf '%s' "$line" | grep -o 'users:((".*"))' | head -1)
  if [ -n "$who" ]; then
    case "$who" in
      *uvicorn*|*python*) kind="local dev backend (uvicorn)";;
      *node*|*vite*)     kind="local dev frontend (vite)";;
      *)                 kind="$who";;
    esac
  elif pgrep -f "[u]vicorn app.main:app" >/dev/null 2>&1; then
    kind="local dev backend (uvicorn)"
  elif pgrep -f "[n]ode .*vite" >/dev/null 2>&1; then
    kind="local dev frontend (vite)"
  else
    kind="unknown process"
  fi
  case "$kind" in
    *"dev backend"*|*"dev frontend"*)
      bad "port $port ($label) is busy: $kind"
      bad "  fix: make dev-stop   (or 'make up' does it automatically)"
      ;;
    *)
      bad "port $port ($label) is busy: $kind"
      bad "  fix: free the port, or set $label in .env (e.g. HTTP_PORT=8080)"
      ;;
  esac
}
check_port "${HTTP_PORT:-80}" HTTP_PORT
check_port "${API_PORT:-8000}" API_PORT

echo "==> Resources"
mem_mb=$(free -m 2>/dev/null | awk '/^Mem:/{print $2}')
if [ -n "${mem_mb:-}" ]; then
  if [ "$mem_mb" -lt 900 ]; then
    warn "only ${mem_mb} MB RAM — the stack needs ~1 GB (postgres+backend+nginx+worker)"
  else
    ok "${mem_mb} MB RAM available"
  fi
fi
disk=$(df -Pm . 2>/dev/null | awk 'NR==2{print $4}')
if [ -n "${disk:-}" ]; then
  if [ "$disk" -lt 2000 ]; then
    warn "only ${disk} MB free disk — the image build needs ~2 GB"
  else
    ok "${disk} MB free disk"
  fi
fi

echo "==> Network"
net_check() {
  if curl -s -m 15 -o /dev/null "$1"; then
    ok "$2 reachable"
  else
    warn "$2 is not reachable — the first build will fail unless images are pre-built"
  fi
}
net_check https://pypi.org/simple/ "pypi.org"
net_check https://registry.npmjs.org/ "npm registry"
net_check https://registry-1.docker.io/v2/ "docker registry"

echo "==> Configuration"
if [ -f .env ]; then
  ok ".env present (per-server overrides)"
  if grep -qE '^ADMIN_PASSWORD=admin$' .env; then
    warn "ADMIN_PASSWORD is still the default 'admin' — change it before going live"
  fi
else
  warn "no .env — defaults are used (admin/admin, port 80/8000)"
  warn "  recommended: cp .env.example .env  and set ADMIN_PASSWORD"
fi
if [ -f backend/.env ]; then
  warn "backend/.env is NOT read by Docker — move its values into the root .env"
fi

echo
if [ "$fail" -eq 0 ]; then
  printf '\033[32mAll checks passed\033[0m — run: docker compose up --build -d\n'
else
  printf '\033[31mSome checks failed\033[0m — fix the FAIL items above\n'
fi
exit "$fail"
