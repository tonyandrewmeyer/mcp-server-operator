# MCP Server Charm for Juju — Plan

## Overview

A **subordinate machine charm** that deploys an MCP (Model Context Protocol) server
on the same machine as a principal charm. The principal declares tools, prompts,
and resources via Juju integration data. The MCP server charm aggregates these
declarations and serves them over streamable HTTP. Ingress is provided via Traefik.

Clients (LLM agents, Claude Code, etc.) connect to the MCP server endpoint and
can discover and invoke the tools/prompts/resources declared by any integrated
principal charm — without the principal needing to implement MCP itself.

## Architecture

```
                  ┌─────────────────────────────────────────────┐
                  │              Machine (Juju unit)            │
                  │                                             │
  Client ──► Traefik ──► MCP Server (subordinate charm)        │
                  │            │                                │
                  │            │ exec / shell commands          │
                  │            ▼                                │
                  │       Principal workload                    │
                  │       (e.g. PostgreSQL, app, etc.)          │
                  └─────────────────────────────────────────────┘
```

- The MCP server runs as a systemd service on the machine.
- On `call_tool`, it executes the declared handler (shell command, script, or
  HTTP call to localhost).
- The subordinate has full access to the machine, so exec-type handlers just run
  directly.

## Integration Interface: `mcp`

The principal charm provides integration data on the `mcp` interface. This is the
contract between the principal and the MCP server charm.

### Integration data schema (principal provides on app data bag)

```json
{
  "tools": [
    {
      "name": "list-databases",
      "description": "List all PostgreSQL databases",
      "input_schema": {
        "type": "object",
        "properties": {},
        "required": []
      },
      "handler": {
        "type": "exec",
        "command": ["sudo", "-u", "postgres", "psql", "-l", "--csv"]
      }
    },
    {
      "name": "run-query",
      "description": "Run a read-only SQL query",
      "input_schema": {
        "type": "object",
        "properties": {
          "query": {"type": "string", "description": "SQL SELECT query"},
          "database": {"type": "string", "description": "Database name"}
        },
        "required": ["query", "database"]
      },
      "handler": {
        "type": "exec",
        "command": ["sudo", "-u", "postgres", "psql", "-d", "{{database}}", "-c", "{{query}}", "--csv"],
        "timeout": 30
      }
    }
  ],
  "prompts": [
    {
      "name": "db-analysis",
      "description": "Analyze database health",
      "arguments": [
        {"name": "database", "description": "Database to analyze", "required": true}
      ],
      "template": "Analyze the health of the {{database}} database. List tables, sizes, and any issues."
    }
  ],
  "resources": [
    {
      "uri": "config://postgresql",
      "name": "PostgreSQL Configuration",
      "description": "Current PostgreSQL configuration",
      "handler": {
        "type": "exec",
        "command": ["cat", "/etc/postgresql/14/main/postgresql.conf"]
      }
    }
  ]
}
```

### Handler types

1. **`exec`** — Run a shell command on the machine. Arguments from the MCP tool
   call are substituted into `{{placeholder}}` positions in the command array.
   - `command`: list of strings (argv)
   - `timeout`: optional, seconds (default 60)
   - `user`: optional, run as this user (default: root)
   - `working_dir`: optional
   - `env`: optional dict of extra environment variables

2. **`http`** — Call a local HTTP endpoint (for workloads that already have an API).
   - `url`: e.g. `http://localhost:8080/api/query`
   - `method`: GET, POST, etc.
   - `body_template`: optional JSON template with `{{placeholder}}` substitution
   - `timeout`: optional, seconds

### Template substitution

`{{param_name}}` in commands, URLs, or body templates gets replaced with the
corresponding argument value from the MCP tool call. Values are validated against
`input_schema` before substitution. For exec handlers, values are passed as
discrete argv elements (no shell interpolation) to prevent injection.

## Charm Structure

```
mcp-charm/
├── charmcraft.yaml          # Charm metadata (subordinate, machine)
├── requirements.txt         # Python dependencies
├── src/
│   ├── charm.py             # Main charm code (ops framework)
│   └── mcp_server.py        # MCP server implementation
├── templates/
│   └── mcp-server.service   # systemd unit file template
└── tests/
    ├── unit/
    │   ├── test_charm.py
    │   └── test_mcp_server.py
    └── integration/
        └── test_integration.py
```

## Charm Metadata (charmcraft.yaml)

```yaml
name: mcp-server
type: charm
title: MCP Server
summary: Expose charm workloads via Model Context Protocol
description: |
  A subordinate charm that deploys an MCP server, allowing principal charms
  to declaratively expose tools, prompts, and resources to MCP clients.

base: ubuntu@24.04
platforms:
  amd64:

subordinate: true

requires:
  juju-info:
    interface: juju-info
    scope: container
  ingress:
    interface: ingress
    limit: 1

provides:
  mcp:
    interface: mcp

config:
  options:
    port:
      type: int
      default: 8081
      description: Port for the MCP server to listen on
    log-level:
      type: string
      default: info
      description: Log level (debug, info, warning, error)
```

Note: The `mcp` interface is provided by this charm, and the principal charm
requires it. This way the principal "requests" MCP exposure and provides its
declarations in the integration data.

Actually — rethinking the direction: the subordinate should **require** the `mcp`
interface, and the **principal provides** it, since the principal is the one
supplying the tool definitions. But in Juju subordinate conventions, the
subordinate typically provides a service. Let's use:

- Subordinate **requires** `juju-info` (to attach to principal)
- Subordinate **requires** `mcp` (to receive tool definitions from principal)
- Wait — a subordinate can't require from its own principal via two interfaces
  easily.

Simpler approach: use `juju-info` for the subordinate attachment, and use a
**peer relation or config** approach... Actually, the cleanest pattern:

- The **principal provides** `mcp` interface (it has the tool definitions)
- The **subordinate requires** `mcp` interface
- The subordinate also requires `juju-info` for attachment (standard subordinate)

When the principal integrates with the MCP server charm, the subordinate gets
deployed on the same machine and reads tool definitions from the `mcp` relation
data bag.

Revised:

```yaml
subordinate: true

requires:
  juju-info:
    interface: juju-info
    scope: container
  mcp:
    interface: mcp
    scope: container

provides:
  ingress:
    interface: ingress
```

Wait, actually for ingress with Traefik the MCP charm would **require** ingress.
And the `mcp` relation needs the scope: container since it's between subordinate
and principal. Let me simplify:

```yaml
subordinate: true

requires:
  mcp:
    interface: mcp
    scope: container
  ingress:
    interface: ingress
```

Using `mcp` with `scope: container` serves double duty: it attaches the
subordinate to the principal AND carries the tool definitions. No need for a
separate `juju-info`. The principal would do:

```yaml
provides:
  mcp:
    interface: mcp
```

And the user runs: `juju integrate my-app:mcp mcp-server:mcp`

## Implementation Plan

### Phase 1: Charm skeleton + MCP server
1. Set up charmcraft.yaml, requirements, and project structure
2. Implement `mcp_server.py` — a standalone MCP server using the `mcp` Python
   SDK with streamable HTTP transport
   - Accepts a JSON config file describing tools/prompts/resources
   - On tool call, executes the declared handler (exec or http)
   - Template substitution with input validation
3. Implement `charm.py`:
   - On `mcp-relation-changed`: read integration data, write config JSON,
     restart MCP server
   - On `install`: install dependencies, set up systemd service
   - On `config-changed`: update port/log-level, restart if needed
   - Health checks via systemd

### Phase 2: Security
4. Input validation — sanitize template substitution (no shell injection for
   exec handlers; use subprocess with list args, never shell=True)
5. Optional allowlist of commands in charm config
6. Rate limiting on the MCP server
7. Auth token support (configurable shared secret or integration with identity)

### Phase 3: Ingress
8. Traefik integration for external access
9. TLS termination via Traefik

### Phase 4: Testing + polish
10. Unit tests for charm and MCP server
11. Integration test with a dummy principal charm
12. Documentation

## Key Design Decisions

1. **systemd service**: The MCP server runs as a long-lived process managed by
   systemd, not re-launched per request. This gives fast response times and
   proper lifecycle management.

2. **JSON config file**: The charm writes a config file that the MCP server
   watches/reloads. This decouples the charm (ops/Python) from the server
   runtime.

3. **No shell=True**: Exec handlers use `subprocess.run` with a list of args.
   Template values are substituted into the argv list as discrete elements,
   never interpolated into a shell string.

4. **Machine-only (for now)**: Direct exec access to the workload. A future k8s
   version could use Pebble exec or require HTTP-only handlers.

## Next Steps

Start with Phase 1: get the charm skeleton and MCP server working end-to-end
with a simple exec-type tool.
