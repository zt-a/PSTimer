.PHONY: up down logs ps restart doctor db-migrate db-revision admin-password backend frontend worker worker-once test

# ── Docker (full stack) ──────────────────────────────────────────────
up:
	docker compose up -d --build

down:
	docker compose down

restart:
	docker compose down && docker compose up -d --build

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
