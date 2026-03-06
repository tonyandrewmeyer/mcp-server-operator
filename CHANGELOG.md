# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Initial project documentation: README, ROADMAP, PLAN, CONTRIBUTING
- Integration schema reference (`docs/integration-schema.md`)
- Apache 2.0 license
- Charm skeleton via `charmcraft init --profile machine` in `charm/`
- Workload project skeleton in `workload/`
- `pyproject.toml` for both charm and workload (ruff, ty, pytest)
- `tox.ini` for charm test environments
- Pre-commit config (ruff, codespell, trailing whitespace, etc.)
- Top-level `Makefile` for format/lint/typecheck/test
- `.gitignore`
- GitHub Actions CI for charm (format, lint, unit tests, integration tests)
- GitHub Actions CI for workload (format, lint, tests)
- GitHub Actions zizmor workflow security audit
- Subordinate machine charm (`charm/`): handles mcp relation, systemd lifecycle, config
- MCP server workload (`workload/`): FastMCP with streamable HTTP, exec/http handlers, template substitution
- Unit tests: 5 charm tests, 15 workload tests
- Demo principal charm (`demo/principal/`) for e2e testing
- End-to-end validation: deploy principal + subordinate, tools/prompts/resources work via HTTP
- CLAUDE.md project guide with code style conventions
- This changelog

- `charmlibs-mcp` Python package (`charmlib/`) with `McpProvider`, `McpRequirer`, and typed dataclass models (`Tool`, `Prompt`, `Resource`, `ExecHandler`, `HttpHandler`, `McpDefinitions`)
- 23 unit tests for charmlib (16 model tests, 7 provider/requirer tests)
- README for charmlib with usage examples

### Changed
- Charm uses `self.load_config(CharmConfig)` and `relation.load(McpRelationData)` instead of raw relation data access
- Import style: `import pathlib` (modules) rather than `from pathlib import Path` (objects)
- UK English throughout all text
- Comments follow full-sentence style, used sparingly to explain why

### Fixed
- Workload server bundled as `charm/src/workload_server.py` (included in packed charm)
- Install hook installs `python3-venv` before creating virtualenv
- FastMCP API: `host`/`port` set in constructor, `Prompt.from_function()`, `FunctionResource`
- Tool handlers use explicit `inspect.Signature` for proper parameter introspection
