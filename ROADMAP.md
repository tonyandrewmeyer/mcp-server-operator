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

## Phase 3: Charm library (`charmlibs-interfaces-mcp`)

- [x] Create `charmlibs-interfaces-mcp` Python package (published to PyPI)
- [x] Provider class — for charms that want to expose tools/prompts/resources via MCP (i.e. the principal charm uses this to set relation data)
- [x] Requirer class — used internally by the mcp-server charm to read relation data
- [x] Typed data models for tools, prompts, resources, and handlers (no pydantic — use dataclasses)
- [x] Documentation and examples for charm authors

This library lets any charm add MCP support with minimal code:
```python
from charmlibs.mcp import McpProvider

mcp = McpProvider(self, "mcp")
mcp.set_tools([...])
```

## Phase 4: Security

- [x] Input validation — validate tool call arguments against declared `input_schema` before handler execution
- [x] No `shell=True` — enforce subprocess list args only (done by design)
- [x] Optional command allowlist in charm config (`command-allowlist`)
- [x] Rate limiting on the MCP server endpoint (`rate-limit` config)
- [x] Auth token support (Bearer token via `auth-token` config)
- [ ] OAuth 2.1 support via identity provider integration (required for MCP clients like Claude Desktop that expect the standard OAuth flow)

## Phase 5: Ingress + TLS

- [ ] Traefik integration for external access
- [ ] TLS termination via Traefik
- [ ] Direct TLS support (certificate relation or config)
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
- [ ] Spread for charm integration tests
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
- [ ] Flesh out SECURITY.md with known security considerations, threat model, and hardening guidance

## Phase 10: Polish + packaging

- [ ] Publish to Charmhub
- [ ] Publish `charmlibs-interfaces-mcp` to PyPI
- [ ] Documentation site (Read the Docs or similar)

## Future: Chaos testing

- [ ] Integration with Litmus operators for chaos testing

## Future: Kubernetes version

- [ ] Separate charm designed for k8s (HTTP-only handlers, sidecar container pattern)
- [ ] Pebble exec support for container access
