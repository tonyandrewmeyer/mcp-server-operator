# Roadmap

## Phase 0: Project infrastructure (current)

- [x] Project documentation (README, ROADMAP, PLAN, CHANGELOG, CONTRIBUTING)
- [x] `pyproject.toml` — project metadata, dependencies, tool config (charm + workload)
- [x] Linting: ruff (format + lint), ty (type checking)
- [x] Pre-commit hooks (ruff, codespell, trailing whitespace, etc.)
- [x] Makefile for common tasks (format, lint, typecheck, test)
- [x] tox for charm test environments
- [x] Test infrastructure (pytest, coverage)
- [x] Charm skeleton via `charmcraft init --profile machine`
- [x] Workload project skeleton
- [ ] GitHub Actions CI (lint, type check, unit tests)

## Phase 1: Core — Charm skeleton + MCP server

- [ ] `charm/charmcraft.yaml` — subordinate machine charm metadata (update from scaffold)
- [ ] `charm/src/charm.py` — ops charm handling `mcp` relation and systemd lifecycle
- [ ] `charm/src/mcp_server.py` — workload management (install, start, stop, configure)
- [ ] `workload/src/server.py` — MCP server with streamable HTTP, dynamic tool/prompt/resource registration from a JSON config file
- [ ] `charm/templates/mcp-server.service` — systemd unit file
- [ ] End-to-end: principal sets relation data, MCP server starts and serves tools

## Phase 2: Security

- [ ] Input validation — validate tool call arguments against declared `input_schema` before handler execution
- [ ] No `shell=True` — enforce subprocess list args only (done by design)
- [ ] Optional command allowlist in charm config
- [ ] Rate limiting on the MCP server endpoint
- [ ] Auth token support (shared secret via config or relation)

## Phase 3: Ingress

- [ ] Traefik integration for external access
- [ ] TLS termination via Traefik
- [ ] Configurable path prefix per principal

## Phase 4: Testing

- [ ] Unit tests for `charm.py`
- [ ] Unit tests for `mcp_server.py` (handler execution, template substitution, schema validation)
- [ ] Integration test with a dummy principal charm
- [ ] CI with GitHub Actions + tox

## Phase 5: Polish + packaging

- [ ] Publish to Charmhub
- [ ] Example principal charm (e.g. a simple app exposing a few tools)
- [ ] Documentation for charm authors wanting to integrate

## Future: Kubernetes version

- [ ] Separate charm designed for k8s (HTTP-only handlers, sidecar container pattern)
- [ ] Pebble exec support for container access
