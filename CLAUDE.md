# Claude Code Project Guide

## Project overview
MCP Server subordinate machine charm for Juju. Deploys an MCP (Model Context Protocol) server
that lets principal charms declaratively expose tools, prompts, and resources to MCP clients.

## Repository structure
- `charm/` — Juju charm (ops framework). Subordinate, attaches via `mcp` relation with `scope: container`.
- `workload/` — Standalone MCP server process (FastMCP, streamable HTTP). Runs as a systemd service.
- `charmlib/` — `charmlibs-mcp` Python package: McpProvider, McpRequirer, typed dataclass models.
- `demo/principal/` — Demo principal charm for e2e testing.
- `docs/` — Documentation (integration schema reference, etc.)

## Code style rules
- **Imports**: Always import modules, not smaller objects. Write `import pathlib` and use `pathlib.Path`, not `from pathlib import Path`. Exception: typing imports (e.g. `from typing import Any`).
- **Language**: Use UK English in all text (e.g. "behaviour", "initialise", "colour").
- **Comments**: Use sparingly to explain *why*, not *what*. Comments are always full sentences with capitalisation and ending punctuation.
- **No pydantic** for data models in the charm library — use dataclasses or plain dicts.
- Formatter/linter: ruff. Type checker: ty. Tests: pytest.
- Charm tests use ops.testing (scenario-style). Workload tests are plain pytest.
- All subprocess calls use list args (never `shell=True`) for security.
- Template substitution uses `{{param}}` syntax in handler commands/URLs.
- Relation data key is `mcp_definitions` (JSON string on app data bag).

## Common commands
```bash
make format      # Format both charm and workload
make lint        # Lint both
make typecheck   # ty check both
make check       # lint + typecheck
make test        # All tests
make test-charm  # Charm unit tests only (via tox)
make test-workload  # Workload tests only
```

## Charm specifics
- charmcraft.yaml is in `charm/`
- Pack with `cd charm && charmcraft pack`
- The charm bundles `workload/src/server.py` as `charm/src/workload_server.py`

## GitHub
- Org: tonyandrewmeyer
- Repo: mcp-server-operator
