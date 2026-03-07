# Configuration Reference

This document describes all configuration options for the MCP Server charm.
Options are set via `juju config mcp-server <option>=<value>`.

## `port`

| | |
|---|---|
| **Type** | int |
| **Default** | `8081` |

Port for the MCP server to listen on.

```bash
juju config mcp-server port=9090
```

## `log-level`

| | |
|---|---|
| **Type** | string |
| **Default** | `"info"` |
| **Accepted values** | `debug`, `info`, `warning`, `error` |

Log level for the MCP server. Set to `debug` for verbose output when
troubleshooting, or `error` to suppress routine messages.

```bash
juju config mcp-server log-level=debug
```

## `auth-token`

| | |
|---|---|
| **Type** | string |
| **Default** | `""` (empty — authentication disabled) |

Bearer token for MCP server authentication. When set, clients must include an
`Authorization: Bearer <token>` header with every request. Leave empty to
disable bearer-token authentication entirely.

When the `oauth` relation is active, OAuth takes precedence and this token is
ignored.

```bash
juju config mcp-server auth-token=my-secret-token
```

## `rate-limit`

| | |
|---|---|
| **Type** | int |
| **Default** | `0` (disabled) |

Maximum number of requests per minute to the MCP server endpoint. Set to `0`
to disable rate limiting.

Rate limiting is applied per server instance, not per client. A single client
can therefore consume the entire quota.

```bash
juju config mcp-server rate-limit=120
```

## `command-allowlist`

| | |
|---|---|
| **Type** | string |
| **Default** | `""` (empty — all commands permitted) |

Space-separated list of executable names that exec handlers are allowed to run.
When empty, all commands are permitted. Only the basename of the first element
of the command list is checked (e.g. `psql` matches `/usr/bin/psql`).

```bash
juju config mcp-server command-allowlist="psql cat ls"
```

## `path-prefix`

| | |
|---|---|
| **Type** | string |
| **Default** | `""` (empty — no prefix, root path) |

URL path prefix for the MCP server endpoint. Used when routing through a
reverse proxy. For example, setting `path-prefix=/postgresql` makes the MCP
endpoint available at `/postgresql/mcp`.

```bash
juju config mcp-server path-prefix=/postgresql
```

## `external-hostname`

| | |
|---|---|
| **Type** | string |
| **Default** | `""` (empty) |

Hostname to use when requesting TLS certificates via the `certificates`
relation. This should be the fully qualified domain name (FQDN) that clients
use to reach the MCP server. Required when using the `certificates` relation.

```bash
juju config mcp-server external-hostname=mcp.example.com
```
