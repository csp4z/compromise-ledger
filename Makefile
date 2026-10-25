.DEFAULT_GOAL := help
.PHONY: help dev lint format typecheck test check schemas sample-exports web api schedule unschedule

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

dev: ## Install the workspace and git hooks
	uv sync --all-packages
	uv run pre-commit install

lint: ## Lint and check formatting (no changes)
	uv run ruff check .
	uv run ruff format --check .

format: ## Apply lint fixes and formatting
	uv run ruff check --fix .
	uv run ruff format .

typecheck: ## Run pyright (strict in schemas/ and crawlers/sdk/)
	uv run pyright

test: ## Run the test suite (offline)
	uv run pytest

check: lint typecheck test ## Everything CI runs on Python code

schemas: ## Regenerate the committed JSON Schema files in schemas/json/
	uv run python -m ledger_schemas.jsonschema

sample-exports: ## Refresh tests/sample-exports/ from the local export (.lake/exports)
	rm -rf tests/sample-exports
	uv run python -m ledger_pipelines.sample $${CL_EXPORTS_DIR:-.lake/exports} tests/sample-exports

web: ## Build the static site from the local export into web/build/
	cd web && pnpm install --frozen-lockfile && pnpm build

api: ## Serve the read-only API on http://127.0.0.1:8000 (docs at /docs)
	uv run ledger-api

schedule: ## macOS: run `ledger run daily` every day with launchd (CL_DAILY_HOUR/MINUTE)
	deploy/launchd/install.sh install

unschedule: ## macOS: remove the daily launchd job
	deploy/launchd/install.sh uninstall
