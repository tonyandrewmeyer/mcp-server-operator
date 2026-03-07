# Architecture and design

This document explains the architectural decisions behind the MCP Server charm:
why it is structured as it is, the trade-offs considered, and the reasoning
behind each major design choice.


## Architecture

### Subordinate charm pattern

The MCP Server charm is a *subordinate* charm. In Juju, a subordinate does not
get its own machine; instead it is deployed onto the same machine as a
*principal* charm via a relation declared with `scope: container`. This means
the subordinate's unit agent and workload share an operating system instance,
filesystem, and network namespace with the principal.

The `mcp` relation that connects principals to the MCP Server charm uses
`scope: container`, which is what makes it a subordinate relation. When a
principal charm relates to `mcp-server`, Juju automatically places an
`mcp-server` unit on the same machine as the principal unit that created the
relation. There is exactly one MCP Server unit per principal unit, co-located
by definition.

### The MCP server as a systemd service

The actual MCP server process runs as a systemd service (`mcp-server.service`)
on the principal's machine. The charm installs the server into
`/opt/mcp-server`, creates a Python virtualenv with the required dependencies,
and writes a systemd unit file that starts the server with the appropriate
command-line arguments.

Because the server runs on the same machine as the principal workload, `exec`
handlers can directly invoke commands that the principal workload provides ---
for example, `psql` for a PostgreSQL charm or `mysql` for a MySQL charm ---
without any network hop or remote execution mechanism.

### Relation data flow

Data flows through the system in a clear pipeline:

1. **Principal sets definitions.** The principal charm uses `McpProvider` (from
   the charm library) to publish an `McpDefinitions` object --- tools, prompts,
   and resources --- as a JSON string in the `mcp_definitions` key of the
   relation's app data bag.

2. **Charm writes config JSON.** When the MCP Server charm receives a
   `relation-changed` event, it uses `McpRequirer` to collect definitions from
   all related providers, merges them, and writes the result to
   `/etc/mcp-server/config.json`.

3. **Server reads config.** On startup, the MCP server process reads
   `config.json` and registers every tool, prompt, and resource with the
   FastMCP framework. A restart of the systemd service picks up any
   configuration changes.

This pipeline is deliberately one-directional. The principal charm never needs
to know about the server process, and the server process never needs to know
about Juju relations.

### Handler execution model

The MCP server supports two handler types:

- **exec handlers** run a command as a subprocess. The `command` field is a list
  of argv elements (never a shell string). Template placeholders like
  `{{query}}` are substituted into individual argv elements before execution.
  The subprocess is run directly via Python's `subprocess.run` with no shell
  involvement.

- **http handlers** make an HTTP request to a local endpoint, typically the
  principal workload's own API. The `url` and optional `body_template` support
  the same `{{param}}` template substitution.

Both handler types support configurable timeouts and, for exec handlers,
optional `user`, `working_dir`, and `env` fields.


## Design decisions

### Why subordinate, not standalone

A standalone charm would run on its own machine and need to reach the
principal's workload over the network to execute commands or call APIs. This
introduces latency, requires authentication and authorisation for the
management channel, and makes `exec` handlers impractical --- you would need
SSH or a remote execution agent.

By running as a subordinate, the MCP server has direct access to the
principal's filesystem and can run commands locally as a subprocess. This is
the simplest and most secure execution model for `exec` handlers.

### Why systemd, not per-request

An alternative would be to start the MCP server on demand for each incoming
request (a CGI-like model). This was rejected because:

- **Startup cost.** Importing FastMCP and loading the config file takes
  non-trivial time. A persistent process eliminates this overhead.
- **Lifecycle management.** systemd provides automatic restart on failure,
  logging integration with journald, and clean shutdown via standard signals.
- **Connection handling.** Streamable HTTP benefits from a long-lived process
  that can manage connections and middleware state (rate limiting, metrics
  counters, active connection gauges).

### Why a JSON config file

The charm (ops framework, Python) and the server (FastMCP, uvicorn) are
separate processes. They need a communication channel for the tool/prompt/
resource definitions. The options considered were:

- **Environment variables.** Too limited for structured, variable-length data.
- **Command-line arguments.** Unwieldy for dozens of tool definitions.
- **A config file.** Simple, human-readable, easy to debug with `cat`. The
  charm writes it; the server reads it at startup.

JSON was chosen over YAML or TOML because it requires no additional parsing
library (Python's `json` module is in the standard library) and is the native
serialisation format for the relation data bag.

This approach also decouples the two codebases cleanly: the charm depends on
`ops` and the charm library, while the server depends on `mcp` and `fastmcp`.
Neither needs to import the other.

### Why no shell=True

Every `subprocess.run` call in both the charm and the server uses a list of
arguments, never a shell string. Python's `subprocess` documentation explicitly
warns against `shell=True` when the command includes user-controlled input,
because shell metacharacters in an argument value could lead to command
injection.

With list-based argv and `shell=False` (the default), each argument is passed
directly to the kernel's `execve` call. There is no shell to interpret
semicolons, pipes, backticks, or variable expansions.

### Why dataclasses, not pydantic

The charm library (`charmlibs-interfaces-mcp`) is consumed by principal charms
as a dependency. Pydantic would add a heavyweight transitive dependency that
every consumer must install. Plain dataclasses:

- Are part of the Python standard library --- no extra dependency.
- Are straightforward to understand and debug.
- Provide sufficient structure for the typed models (`Tool`, `Prompt`,
  `Resource`, `ExecHandler`, `HttpHandler`, `McpDefinitions`).

The trade-off is that validation is manual (the `to_dict` / `from_dict` methods
handle serialisation, and the server validates arguments against the declared
JSON Schema at call time), but this is acceptable for the relatively simple
data shapes involved.

### Why template substitution with {{param}}

Tool and resource handlers need to incorporate user-supplied arguments into
commands and URLs. The `{{param}}` syntax was chosen because:

- **Discrete argv elements.** Each element in the `command` list is substituted
  independently. A `{{query}}` placeholder in one argv element is replaced with
  the argument value as a single string. It never crosses argv boundaries or
  gets shell-interpreted, because there is no shell.
- **Explicit and visible.** Double braces are easy to spot in configuration and
  do not collide with Python format strings or Jinja2 (which uses `{% %}` for
  logic).
- **Simple implementation.** A single regex (`\{\{(\w+)\}\}`) handles all
  substitution. There is no expression language, no conditionals, and no
  nesting --- by design.

### Why FastMCP with streamable HTTP

The Model Context Protocol defines several transports. Streamable HTTP was
chosen because:

- **Firewall-friendly.** It uses standard HTTP on a single port, unlike
  WebSocket or stdio transports.
- **Stateless mode.** The server runs with `stateless_http=True`, meaning each
  request is independent. This simplifies the server, avoids session management,
  and makes it straightforward to restart the process without breaking clients.
- **Broad client support.** Streamable HTTP is the recommended transport for
  remote MCP servers and is supported by Claude Code and other major MCP
  clients.

FastMCP was chosen as the server framework because it is the official
high-level Python SDK for MCP, providing tool/prompt/resource registration,
input schema introspection, and transport handling out of the box.


## Security model

The MCP server implements defence in depth: multiple independent layers that
each reduce the attack surface, so that a failure in one layer does not
compromise the system.

### Input validation

Before any handler executes, the server validates the caller's arguments
against the tool's declared JSON Schema. This catches type mismatches, missing
required fields, and unexpected extra arguments before they reach the handler.

### Command allowlist

The `command-allowlist` configuration option restricts which executables `exec`
handlers are permitted to run. When set, the server checks the first element of
each command against the allowlist and rejects any command whose executable is
not explicitly permitted. This prevents a misconfigured tool definition from
running arbitrary binaries.

### No shell interpolation

As discussed above, all subprocess calls use list-based argv with no shell.
Even if an attacker could influence argument values through the MCP protocol,
they cannot inject shell metacharacters because there is no shell to interpret
them.

### Rate limiting

The server supports per-instance rate limiting via the `rate-limit`
configuration option. When enabled, a sliding-window counter rejects requests
that exceed the configured threshold, returning HTTP 429. This provides basic
protection against denial-of-service and runaway clients.

### Authentication

Two authentication mechanisms are supported:

- **Bearer token.** The simpler option. When the `auth-token` configuration
  option is set, the server requires an `Authorization: Bearer <token>` header
  on every request. Requests without a valid token receive HTTP 401. This is
  suitable for single-tenant deployments or development environments.

- **OAuth 2.1 resource server mode.** For production deployments, the server
  can integrate with an OAuth 2.1 provider (via the `oauth` Juju relation). It
  supports two token validation strategies:
  - **JWT validation.** The server fetches the provider's JWKS (JSON Web Key
    Set) and validates JWT access tokens locally. This is fast and does not
    require a network call per request.
  - **Token introspection.** For opaque (non-JWT) tokens, the server calls the
    provider's introspection endpoint to verify each token. This requires
    network access to the OAuth provider but supports a wider range of token
    formats.

### Transport encryption

The server supports TLS via the `certificates` Juju relation. When a TLS
provider supplies a certificate and private key, the charm writes them to disk
and configures uvicorn to serve HTTPS. This encrypts traffic between MCP
clients and the server.

For deployments behind a reverse proxy (via the `reverse-proxy` relation), TLS
can alternatively be terminated at the proxy, with the server running plain
HTTP on localhost.


## Observability architecture

The MCP server integrates with the Canonical Observability Stack (COS) to
provide metrics, tracing, and structured logging.

### Metrics

The server exposes Prometheus metrics on its `/metrics` endpoint using the
`prometheus-client` library. Four metric families are defined:

- `mcp_requests_total` --- a counter of all HTTP requests, labelled by method
  and status code.
- `mcp_request_duration_seconds` --- a histogram of request latency, labelled
  by method.
- `mcp_tool_calls_total` --- a counter of tool invocations, labelled by tool
  name and status (success or error).
- `mcp_active_connections` --- a gauge of currently active connections.

These metrics are recorded by a Starlette middleware that wraps every request,
so they capture the full lifecycle including authentication and rate limiting.

### COS integration

The charm provides a `cos-agent` relation (interface `cos_agent`). When related
to `grafana-agent` (the COS subordinate), the agent scrapes the `/metrics`
endpoint and forwards the data to Prometheus in the COS deployment. The charm
also ships Grafana dashboard JSON and Prometheus alert rules so that dashboards
and alerts are available out of the box.

### Tracing

When the `charm-tracing` relation is connected to a Tempo instance (via the
`tracing` interface), the server enables OpenTelemetry tracing:

- An ASGI middleware (`OpenTelemetryMiddleware`) instruments every HTTP request
  with a trace span.
- Spans are exported via OTLP over HTTP to the Tempo endpoint provided by the
  relation.
- The `BatchSpanProcessor` batches span exports to reduce overhead.

This gives operators request-level visibility into the MCP server's behaviour,
including latency breakdowns across middleware layers.

### Structured logging

The server supports a `--log-format json` mode (enabled by default in the
systemd unit) that outputs structured JSON log lines. Each line includes a
timestamp, logger name, level, and message. This format is designed for
ingestion by Loki (via Grafana Agent reading journald) and enables structured
queries across log fields.
