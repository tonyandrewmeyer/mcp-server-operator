# MCP Server Charm for Juju

A subordinate machine charm that deploys a [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server, allowing principal charms to declaratively expose tools, prompts, and resources to MCP clients (LLM agents, Claude Code, etc.) — without implementing MCP themselves.

## How it works

```
                  ┌─────────────────────────────────────────────┐
                  │              Machine (Juju unit)            │
                  │                                             │
  Client ──► Traefik ──► MCP Server (subordinate charm)        │
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
5. Ingress is provided via **Traefik** integration.

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

## Deployment

```bash
# Deploy a principal charm
juju deploy postgresql

# Deploy the MCP server subordinate
juju deploy mcp-server

# Integrate them
juju integrate postgresql:mcp mcp-server:mcp

# Optionally add ingress
juju deploy traefik
juju integrate mcp-server:ingress traefik:ingress
```

## Configuration

| Option    | Type   | Default | Description                          |
|-----------|--------|---------|--------------------------------------|
| port      | int    | 8081    | Port for the MCP server to listen on |
| log-level | string | info    | Log level (debug, info, warning, error) |

## Status

This project is in early development. See [ROADMAP.md](ROADMAP.md) for planned work.

## License

Apache 2.0
