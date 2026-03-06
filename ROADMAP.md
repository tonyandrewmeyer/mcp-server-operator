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
- [x] GitHub Actions CI: charm (format, lint, unit tests, integration tests)
- [x] GitHub Actions CI: workload (format, lint, tests)
- [x] GitHub Actions: zizmor workflow security audit

## Phase 1: Core — Charm skeleton + MCP server

- [x] `charm/charmcraft.yaml` — subordinate machine charm metadata
- [x] `charm/src/charm.py` — ops charm handling `mcp` relation and systemd lifecycle
- [x] `charm/src/mcp_server.py` — workload management (install, start, stop, configure)
- [x] `workload/src/server.py` — MCP server with streamable HTTP, dynamic tool/prompt/resource registration from a JSON config file
- [x] systemd unit (template in mcp_server.py)
- [x] Unit tests: 5 charm tests, 15 workload tests
- [x] End-to-end validated: demo principal sets relation data, MCP server starts, tools/prompts/resources callable via HTTP

## Phase 2: Code quality

- [x] Use `self.load_config` and `relation.save`/`relation.load` instead of raw relation data values
- [x] Fix import style: `import pathlib` not `from pathlib import Path` (modules, not objects)
- [x] UK English throughout
- [x] Comments: full sentences, sparingly, explain why not what

## Phase 3: Charm library (`charmlibs-mcp`)

- [ ] Create `charmlibs-mcp` Python package (published to PyPI)
- [ ] Provider class — for charms that want to expose tools/prompts/resources via MCP (i.e. the principal charm uses this to set relation data)
- [ ] Requirer class — used internally by the mcp-server charm to read relation data
- [ ] Typed data models for tools, prompts, resources, and handlers (no pydantic — use dataclasses)
- [ ] Documentation and examples for charm authors

This library lets any charm add MCP support with minimal code:
```python
from charmlibs.mcp import McpProvider

mcp = McpProvider(self, "mcp")
mcp.set_tools([...])
```

## Phase 4: Security

- [ ] Input validation — validate tool call arguments against declared `input_schema` before handler execution
- [ ] No `shell=True` — enforce subprocess list args only (done by design)
- [ ] Optional command allowlist in charm config
- [ ] Rate limiting on the MCP server endpoint
- [ ] Auth token support (shared secret via config or relation)

## Phase 5: Ingress

- [ ] Traefik integration for external access
- [ ] TLS termination via Traefik
- [ ] Configurable path prefix per principal

## Phase 6: Observability (COS integration)

- [ ] Tracing for the charm (tempo integration)
- [ ] Tracing for the MCP server workload
- [ ] Metrics endpoint (prometheus integration)
- [ ] Log forwarding (loki integration)
- [ ] Grafana dashboard
- [ ] SLOs via sloth-k8s charm

## Phase 7: Testing

- [ ] Unit tests for `charm.py`
- [ ] Unit tests for `mcp_server.py` (handler execution, template substitution, schema validation)
- [ ] Integration test with a dummy principal charm
- [ ] CI with GitHub Actions + tox

## Phase 8: Demo

- [ ] Example principal charm showing how easy it is to add MCP to an existing charm
- [ ] End-to-end demo: deploy principal + mcp-server, connect Claude Code, invoke tools
- [ ] Screencast / README walkthrough

## Phase 9: Documentation (Diataxis)

- [ ] Tutorials — step-by-step guide to adding MCP to your charm
- [ ] How-to guides — specific tasks (add a tool, configure ingress, etc.)
- [ ] Reference — integration schema, config options, API docs
- [ ] Explanation — architecture, design decisions, security model

## Phase 10: Polish + packaging

- [ ] Publish to Charmhub
- [ ] Publish `charmlibs-mcp` to PyPI
- [ ] Documentation site (Read the Docs or similar)

## Future: Kubernetes version

- [ ] Separate charm designed for k8s (HTTP-only handlers, sidecar container pattern)
- [ ] Pebble exec support for container access
