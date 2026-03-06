.PHONY: format lint typecheck check test test-charm test-workload clean

## Format code in both charm and workload
format:
	cd charm && uv run ruff format src tests
	cd charm && uv run ruff check --fix src tests
	cd workload && uv run ruff format src tests
	cd workload && uv run ruff check --fix src tests

## Run linters
lint:
	cd charm && uv run ruff check src tests
	cd charm && uv run ruff format --check --diff src tests
	cd charm && uv run codespell .
	cd workload && uv run ruff check src tests
	cd workload && uv run ruff format --check --diff src tests

## Run type checkers
typecheck:
	cd charm && uv run ty check
	cd workload && uv run ty check

## Run all checks (format check, lint, typecheck)
check: lint typecheck

## Run all tests
test: test-charm test-workload

## Run charm unit tests
test-charm:
	cd charm && tox run -e unit

## Run workload tests
test-workload:
	cd workload && uv run pytest tests/ -v

## Clean build artifacts
clean:
	rm -rf charm/.tox charm/build charm/*.charm
	rm -rf workload/.tox workload/build
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name .coverage -delete 2>/dev/null || true
