# MCP Server Charm for Juju

A subordinate machine charm that deploys a [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server, allowing principal charms to declaratively expose tools, prompts, and resources to MCP clients (LLM agents, Claude Code, etc.) — without implementing MCP themselves.

## How it works

```
                  ┌─────────────────────────────────────────────┐
                  │              Machine (Juju unit)            │
                  │                                             │
  Client ──► HAProxy ──► MCP Server (subordinate charm)         │
                  │            │                                │
                  │            │ exec / http                    │
                  │            ▼                                │
                  │       Principal workload                    │
                  │       (e.g. PostgreSQL, app, etc.)          │
                  └─────────────────────────────────────────────┘
```

1. A principal charm (e.g. PostgreSQL) **provides** the `mcp` interface, declaring its tools, prompts, and resources in the relation data bag.
2. The MCP server charm attaches as a **subordinate** (via `scope: container`) and reads those declarations.
3. It runs a Python MCP server (using the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)) as a **systemd service** on the same machine.
4. When an MCP client calls a tool, the server executes the declared handler — either a shell command (`exec`) or a local HTTP call (`http`).
5. Ingress is provided via **HAProxy** integration.

## Integration interface

The principal charm provides tool/prompt/resource definitions as JSON in the `mcp` relation's app data bag. Example:

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
    }
  ],
  "prompts": [],
  "resources": []
}
```

### Handler types

- **`exec`** — Run a command on the machine. Arguments are substituted into `{{placeholder}}` positions in the command array. Uses `subprocess.run` with list args (no shell injection).
- **`http`** — Call a local HTTP endpoint. Supports method, URL, and body templates.

See [docs/integration-schema.md](docs/integration-schema.md) for the full schema reference.

### Charm library

The `charmlibs-interfaces-mcp` package provides typed dataclasses and helper classes for working with the `mcp` interface:

```python
from charmlibs.interfaces import mcp

self.mcp = mcp.McpProvider(self, "mcp")
self.mcp.set_tools([
    mcp.Tool(name="list-dbs", description="List databases",
         handler=mcp.ExecHandler(command=["psql", "-l", "--csv"])),
])
```

Install with `pip install charmlibs-interfaces-mcp`. See the [charmlib README](charmlib/README.md) for full details.

## Deployment

```bash
# Deploy a principal charm
juju deploy postgresql

# Deploy the MCP server subordinate
juju deploy mcp-server

# Integrate them
juju integrate postgresql:mcp mcp-server:mcp

# HAProxy ingress
juju integrate mcp-server:reverse-proxy haproxy:reverseproxy

# TLS
juju integrate mcp-server:certificates easyrsa:client

# OAuth
juju integrate mcp-server:oauth identity-platform:oauth

# COS observability
juju integrate mcp-server:cos-agent grafana-agent:cos-agent
```

## Configuration

| Option | Type | Default | Description |
|---|---|---|---|
| port | int | 8081 | Port for the MCP server to listen on |
| log-level | string | info | Log level (debug, info, warning, error) |
| auth-token | string | "" | Bearer token for authentication (empty = disabled) |
| rate-limit | int | 0 | Maximum requests per minute (0 = disabled) |
| command-allowlist | string | "" | Space-separated allowed executable names (empty = all allowed) |
| path-prefix | string | "" | URL path prefix for MCP endpoint (e.g. /postgresql) |
| external-hostname | string | "" | FQDN for TLS certificate requests |

## Documentation

- [Tutorial](docs/tutorial.md)
- [How-to guides](docs/how-to/)
- [Reference](docs/reference/)
- [Architecture & design](docs/explanation.md)
- [Integration schema](docs/integration-schema.md)

## Status

This project is under active development. See [ROADMAP.md](ROADMAP.md) for planned work.
