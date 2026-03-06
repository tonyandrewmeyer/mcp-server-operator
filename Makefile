.PHONY: format lint typecheck check test test-charm test-workload test-charmlib sync-workload pack clean

## Format code in charm, workload, and charmlib
format:
	cd charm && uv run ruff format src tests
	cd charm && uv run ruff check --fix src tests
	cd workload && uv run ruff format src tests
	cd workload && uv run ruff check --fix src tests
	cd charmlib && uv run ruff format src tests
	cd charmlib && uv run ruff check --fix src tests

## Run linters
lint:
	cd charm && uv run ruff check src tests
	cd charm && uv run ruff format --check --diff src tests
	cd charm && uv run codespell .
	cd workload && uv run ruff check src tests
	cd workload && uv run ruff format --check --diff src tests
	cd charmlib && uv run ruff check src tests
	cd charmlib && uv run ruff format --check --diff src tests

## Run type checkers
typecheck:
	cd charm && uv run ty check
	cd workload && uv run ty check

## Run all checks (format check, lint, typecheck)
check: lint typecheck

## Run all tests
test: test-charm test-workload test-charmlib

## Run charm unit tests
test-charm: sync-workload
	cd charm && tox run -e unit

## Run workload tests
test-workload:
	cd workload && uv run pytest tests/ -v

## Run charmlib tests
test-charmlib:
	cd charmlib && uv run pytest tests/ -v

## Copy workload source into charm/src/ for packaging
sync-workload:
	cp workload/src/server.py charm/src/workload_server.py
	cp workload/src/token_verifier.py charm/src/token_verifier.py

## Pack the charm (copies workload source first)
pack: sync-workload
	cd charm && charmcraft pack

## Clean build artifacts
clean:
	rm -rf charm/.tox charm/build charm/*.charm
	rm -rf workload/.tox workload/build
	rm -rf charmlib/build charmlib/dist
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name .coverage -delete 2>/dev/null || true
