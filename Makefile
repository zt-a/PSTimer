.PHONY: up down logs ps db-migrate db-revision backend frontend worker worker-once test

# ── Docker (full stack) ──────────────────────────────────────────────
up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

# ── Database ────────────────────────────────────────────────────────
db-migrate:
	docker compose exec backend alembic upgrade head

db-revision:
	docker compose exec backend alembic revision --autogenerate -m "$(m)"

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
