# How to configure ingress

This guide shows how to route external traffic to the MCP server through a
reverse proxy using the HAProxy integration.

## Prerequisites

- A deployed `mcp-server` subordinate charm.
- The `haproxy` charm available in your model.

## HAProxy integration

The MCP server charm has a `reverse-proxy` relation that speaks the
`haproxy-route` interface. When the relation is established, the MCP server
automatically provides its address, port, and scheme to HAProxy.

### Deploy and relate HAProxy

```bash
juju deploy haproxy
juju integrate mcp-server:reverse-proxy haproxy:reverseproxy
```

Once related, HAProxy will begin forwarding traffic to the MCP server's
configured port (default 8081).

## Set path-prefix for multi-app routing

When multiple MCP server instances share a single HAProxy, use the
`path-prefix` config option to give each one a distinct URL path. For
example, if you have MCP servers for both PostgreSQL and MySQL:

```bash
juju config mcp-server path-prefix="/postgresql"
```

With this configuration:

- The MCP endpoint is available at `/postgresql/mcp`.
- The health check is available at `/postgresql/health`.
- The metrics endpoint is available at `/postgresql/metrics`.

A second MCP server for MySQL could use:

```bash
juju config mcp-server path-prefix="/mysql"
```

The path prefix is automatically communicated to HAProxy via the relation
data, so no manual HAProxy configuration is required.

### Reset to root path

To remove the prefix and serve from the root path:

```bash
juju config mcp-server path-prefix=""
```

## Health check endpoint

The MCP server exposes a lightweight health check endpoint that returns a
JSON response with the server status. HAProxy and other load balancers can
use this for backend health monitoring.

| Configuration   | Health check path     |
|-----------------|-----------------------|
| No path prefix  | `/health`             |
| With prefix     | `/<prefix>/health`    |

Example response:

```json
{"status": "ok"}
```

To verify the health endpoint manually:

```bash
curl http://<unit-address>:8081/health
```

Or, when using a path prefix:

```bash
curl http://<unit-address>:8081/postgresql/health
```

## Combining ingress with TLS

When HAProxy handles TLS termination, the MCP server itself can run on plain
HTTP. See [How to configure TLS](configure-tls.md) for details on both
direct TLS and TLS via reverse proxy.
