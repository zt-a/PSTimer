.PHONY: up down logs ps restart doctor dev-stop db-migrate db-revision admin-password backend frontend worker worker-once test

# ── Docker (full stack) ──────────────────────────────────────────────
# Local dev servers are stopped first: they hold ports 80/8000 and would
# make the Docker containers fail with "address already in use".
up:
	@bash scripts/dev-stop.sh
	docker compose down --remove-orphans >/dev/null 2>&1 || true
	docker compose up -d --build
	@bash scripts/wait-healthy.sh 120

down:
	docker compose down

restart:
	docker compose down && $(MAKE) up

# Stop the local dev servers (uvicorn/vite) so Docker can use ports 80/8000
dev-stop:
	@bash scripts/dev-stop.sh

# Pre-flight diagnostics (ports, compose version, RAM, disk, .env)
doctor:
	@bash scripts/doctor.sh

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

# ── Database ────────────────────────────────────────────────────────
db-migrate:
	docker compose exec backend alembic upgrade head

db-revision:
	docker compose exec backend alembic revision --autogenerate -m "$(m)"

# Reset the admin password to ADMIN_PASSWORD from the root .env
admin-password:
	docker compose exec backend python -m app.seed --reset-password

# ── Local (no Docker) ────────────────────────────────────────────────
backend:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

# History retention worker (purges completed sessions older than
# HISTORY_RETENTION_DAYS). Runs forever; use worker-once for a single pass.
worker:
	cd backend && . .venv/bin/activate && python -m app.worker

worker-once:
	cd backend && . .venv/bin/activate && python -m app.worker --once

test:
	cd backend && . .venv/bin/activate && pytest -q
