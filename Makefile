API := apps/api
WEB := apps/web
SIM := apps/sim

API_HINT := Run api targets inside the API devcontainer.
WEB_HINT := Run web targets inside the Web devcontainer.
SIM_HINT := Run sim targets inside the APSIM devcontainer.

# Fails with a readable message when a tool is missing, e.g. running web targets in the api container
require = @command -v $(1) >/dev/null 2>&1 || { echo "error: '$(1)' not found. $(2)"; exit 1; }

.DEFAULT_GOAL := help
.PHONY: help api-setup api-install api-dev api-lint api-format api-test api-check \
	sim-setup sim-install sim-dev sim-lint sim-format sim-test sim-check \
	migration migrate migrate-down db-reset web-setup web-dev web-lint web-typecheck web-build web-check \
	up down logs hooks

help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "} \
		/^##@/ {printf "\n\033[1m%s\033[0m\n", substr($$0, 5)} \
		/^[a-zA-Z_-]+:.*## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

##@ API (run in the API devcontainer)

api-setup: api-install migrate ## Install deps and apply migrations (run after pulling)

api-install: ## Install/update Python deps
	$(call require,uv,$(API_HINT))
	cd $(API) && uv sync

api-dev: ## Start the API with auto-reload on :8000
	$(call require,uv,$(API_HINT))
	cd $(API) && uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

api-lint: ## Lint and check formatting (same as CI)
	$(call require,uv,$(API_HINT))
	cd $(API) && uv run ruff check . && uv run ruff format --check .

api-format: ## Auto-fix lint issues and format code
	$(call require,uv,$(API_HINT))
	cd $(API) && uv run ruff check --fix . && uv run ruff format .

api-test: ## Run tests, pass pytest flags with args="-k health -x"
	$(call require,uv,$(API_HINT))
	cd $(API) && uv run pytest $(args)

api-check: api-lint api-test ## Everything CI runs for the API

##@ APSIM (run in APSIM devcontainer)

sim-setup: sim-install

sim-install: ## Install/update Python deps
	$(call require,uv,$(SIM_HINT))
	cd $(SIM) && uv sync

sim-dev: ## Start the SIM with auto-reload on :8001
	$(call require,uv,$(SIM_HINT))
	cd $(SIM) && uv run uvicorn sim.main:app --host 0.0.0.0 --port 8001 --reload

sim-lint: ## Lint and check formatting (same as CI)
	$(call require,uv,$(SIM_HINT))
	cd $(SIM) && uv run ruff check . && uv run ruff format --check .

sim-format: ## Auto-fix lint issues and format code
	$(call require,uv,$(SIM_HINT))
	cd $(SIM) && uv run ruff check --fix . && uv run ruff format .

sim-test: ## Run tests, pass pytest flags with args="-k health -x"
	$(call require,uv,$(SIM_HINT))
	cd $(SIM) && uv run pytest $(args)

sim-check: sim-lint sim-test ## Everything CI runs for the SIM

##@ Database (run in the API devcontainer)

migration: ## Generate a migration from model changes: make migration m="add sensors"
	@test -n "$(m)" || { echo 'usage: make migration m="describe the change"'; exit 1; }
	$(call require,uv,$(API_HINT))
	cd $(API) && uv run alembic revision --autogenerate -m "$(m)"

migrate: ## Apply all pending migrations
	$(call require,uv,$(API_HINT))
	cd $(API) && uv run alembic upgrade head

migrate-down: ## Roll back the latest migration
	$(call require,uv,$(API_HINT))
	cd $(API) && uv run alembic downgrade -1

db-reset: ## Drop everything and re-run all migrations (deletes all data!)
	$(call require,uv,$(API_HINT))
	cd $(API) && uv run alembic downgrade base && uv run alembic upgrade head

##@ Web (run in the Web devcontainer)

web-setup: ## Install/update npm deps (run after pulling)
	$(call require,npm,$(WEB_HINT))
	cd $(WEB) && npm install

web-dev: ## Start the Vite dev server on :5173
	$(call require,npm,$(WEB_HINT))
	cd $(WEB) && npm run dev -- --host 0.0.0.0

web-lint: ## Run ESLint
	$(call require,npm,$(WEB_HINT))
	cd $(WEB) && npm run lint

web-typecheck: ## Type-check with tsc
	$(call require,npm,$(WEB_HINT))
	cd $(WEB) && npm run typecheck

web-build: ## Production build
	$(call require,npm,$(WEB_HINT))
	cd $(WEB) && npm run build

web-check: web-lint web-typecheck web-build ## Everything CI runs for the web app

##@ Repo

hooks: ## Enable the git pre-commit hook (devcontainers do this on start)
	git config core.hooksPath .githooks

##@ Docker (run on your host machine)

up: ## Build and start all services
	docker compose up --build

down: ## Stop all services
	docker compose down

logs: ## Follow logs, optionally for one service: make logs s=api
	docker compose logs -f $(s)
