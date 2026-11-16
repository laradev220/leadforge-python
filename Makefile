# LeadForge AI — Development Makefile
# Targets for local dev without Docker.

.PHONY: setup install-deps install-playwright db-create db-migrate \
        run-api run-discovery-worker run-all-workers run-all lint typecheck test \
        clean kill-api kill-all-workers \
        check-db check-redis check-dotenv check-db-migrated check-all

# ── Setup ──────────────────────────────────────────────────────────────────

setup: install-deps install-playwright db-create db-migrate
	@echo "✓ Setup complete. Run 'make run-api' to start."

install-deps:
	uv sync --all-packages
	@echo "✓ Dependencies installed (lockfile, incl. workspace members)"

install-playwright:
	/usr/bin/playwright install chromium
	@echo "✓ Playwright Chromium installed"

db-create:
	@echo "Creating database 'leadforge-python' if it doesn't exist..."
	-createdb -h localhost -p 5432 -U postgres leadforge-python 2>/dev/null || \
	 echo "Database may already exist (ok)"
	@echo "✓ Database ready"

db-migrate:
	uv run alembic upgrade head
	@echo "✓ Migrations applied"

# ── Run Services ────────────────────────────────────────────────────────────

run-api:
	uv run uvicorn leadforge_api.main:app --host 0.0.0.0 --port 8000 --reload

run-discovery-worker:
	uv run python -m leadforge_discovery_worker

run-website-worker:
	uv run python -m leadforge_website_worker

run-contact-worker:
	uv run python -m leadforge_contact_worker

run-social-worker:
	uv run python -m leadforge_social_worker

run-verification-worker:
	uv run python -m leadforge_verification_worker

run-scoring-worker:
	uv run python -m leadforge_scoring_worker

run-export-worker:
	uv run python -m leadforge_export_worker

run-scheduler-worker:
	uv run python -m leadforge_scheduler_worker

run-webhook-worker:
	uv run python -m leadforge_webhook_worker

LOG_DIR := logs

run-all-workers:
	@mkdir -p $(LOG_DIR)
	@echo "Starting all 9 workers — logs go to logs/<worker>.log"
	uv run python -m leadforge_discovery_worker > $(LOG_DIR)/discovery.log 2>&1 &
	uv run python -m leadforge_website_worker   > $(LOG_DIR)/website.log 2>&1 &
	uv run python -m leadforge_contact_worker   > $(LOG_DIR)/contact.log 2>&1 &
	uv run python -m leadforge_social_worker    > $(LOG_DIR)/social.log 2>&1 &
	uv run python -m leadforge_verification_worker > $(LOG_DIR)/verification.log 2>&1 &
	uv run python -m leadforge_scoring_worker   > $(LOG_DIR)/scoring.log 2>&1 &
	uv run python -m leadforge_export_worker    > $(LOG_DIR)/export.log 2>&1 &
	@echo "✓ All workers started"
	@echo ""
	@echo "Watch all logs:     tail -f logs/*.log"
	@echo "Watch one worker:   tail -f logs/discovery.log"
	@echo "Stop all workers:   make kill-all-workers"

# ── Pre-flight checks ─────────────────────────────────────────────────────

.PHONY: check-db check-redis check-dotenv check-db-migrated

check-db:
	@pg_isready -h localhost -p 5432 -U postgres 2>/dev/null || { echo "❌ Postgres not running on localhost:5432"; exit 1; }
	@echo "✓ Postgres is running"

check-redis:
	@redis-cli -h localhost -p 6379 ping 2>/dev/null | grep -q PONG || { echo "❌ Redis not running on localhost:6379"; exit 1; }
	@echo "✓ Redis is running"

check-dotenv:
	@test -f .env || { echo "❌ .env file not found — copy .env.example or create one"; exit 1; }
	@echo "✓ .env file found"

check-db-migrated:
	@PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres -d leadforge-python -tAc 'SELECT version_num FROM alembic_version;' 2>/dev/null | grep -q . || { echo "❌ Migrations not applied — run 'make db-migrate'"; exit 1; }
	@echo "✓ Migrations up to date"

check-all: check-db check-redis check-dotenv check-db-migrated
	@echo "══════════════════════════════════════════════"
	@echo "  All pre-flight checks passed!"
	@echo "══════════════════════════════════════════════"

run-all:
	@echo "══════════════════════════════════════════════"
	@echo "  LeadForge — Starting API + all 6 workers"
	@echo "══════════════════════════════════════════════"
	@echo ""
	@echo "── Pre-flight checks ──"
	@$(MAKE) check-all --no-print-directory
	@echo ""
	@echo "── Starting workers ──"
	@$(MAKE) run-all-workers --no-print-directory
	@echo ""
	@echo "── Starting API ──"
	@echo "  API will be available at http://localhost:8000"
	@echo ""
	uv run uvicorn leadforge_api.main:app --host 0.0.0.0 --port 8000 --reload

# ── Quality ─────────────────────────────────────────────────────────────────

lint:
	uv run ruff check packages/ apps/ workers/

typecheck:
	uv run mypy packages/ apps/ workers/ --ignore-missing-imports

test:
	uv run pytest tests/ -v --tb=short

test-unit:
	uv run pytest tests/unit/ -v --tb=short

test-integration:
	uv run pytest tests/integration/ -v --tb=short

# ── Cleanup ────────────────────────────────────────────────────────────────

kill-api:
	-pkill -f "leadforge_api.main:app" 2>/dev/null || true
	@echo "✓ API stopped"

kill-all-workers:
	@echo "Stopping all workers..."
	-pkill -f "leadforge_discovery_worker" 2>/dev/null || true
	-pkill -f "leadforge_website_worker" 2>/dev/null || true
	-pkill -f "leadforge_contact_worker" 2>/dev/null || true
	-pkill -f "leadforge_social_worker" 2>/dev/null || true
	-pkill -f "leadforge_verification_worker" 2>/dev/null || true
	-pkill -f "leadforge_scoring_worker" 2>/dev/null || true
	-pkill -f "leadforge_export_worker" 2>/dev/null || true
	-pkill -f "leadforge_scheduler_worker" 2>/dev/null || true
	-pkill -f "leadforge_webhook_worker" 2>/dev/null || true
	@echo "✓ All workers stopped"

clean:
	rm -rf .venv/
	rm -rf exports/
	rm -rf logs/
	@echo "✓ Cleaned up"
