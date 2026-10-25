.DEFAULT_GOAL := help
.PHONY: help dev lint format typecheck test check schemas

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
