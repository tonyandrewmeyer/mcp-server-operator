# How to configure authentication

This guide shows how to secure the MCP server endpoint with authentication,
rate limiting, and command restrictions.

## Prerequisites

- A deployed `mcp-server` subordinate charm.

## Bearer token authentication

The simplest authentication method is a static bearer token. When set,
clients must include an `Authorization: Bearer <token>` header with every
request.

### Set the token

```bash
juju config mcp-server auth-token="my-secret-token-here"
```

### Client usage

```bash
curl -H "Authorization: Bearer my-secret-token-here" \
     http://<address>:8081/mcp
```

### Disable token authentication

Clear the config value to disable bearer token auth:

```bash
juju config mcp-server auth-token=""
```

## OAuth 2.1 via an identity provider

For production deployments, the MCP server supports OAuth 2.1 authentication
through the `oauth` relation. This enables JWT-based or opaque token
validation against an external identity provider.

### Relate to an OAuth provider

```bash
juju integrate mcp-server:oauth identity-provider:oauth
```

The MCP server charm reads the following from the relation data:

- Issuer URL
- JWKS endpoint (for JWT validation)
- Introspection endpoint (for opaque token validation)
- Client ID and client secret (stored as a Juju secret)

Once the relation is established, the server validates incoming bearer tokens
against the identity provider. No manual configuration is required beyond
creating the relation.

### How token validation works

- **JWT tokens:** The server fetches the JWKS from the provider and validates
  the token signature, issuer, and expiry locally.
- **Opaque tokens:** The server calls the introspection endpoint to validate
  the token with the provider.

The identity provider communicates which mode to use via the relation data.

### Removing OAuth

Breaking the relation disables OAuth validation. If `auth-token` is also
empty, the server will accept unauthenticated requests:

```bash
juju remove-relation mcp-server:oauth identity-provider:oauth
```

### Combining OAuth with bearer token

If both OAuth and `auth-token` are configured, OAuth takes precedence. The
static bearer token is ignored while the OAuth relation is active.

## Rate limiting

Use the `rate-limit` config to cap the number of requests per minute to the
MCP server endpoint. This protects against accidental or malicious overuse.

### Enable rate limiting

```bash
juju config mcp-server rate-limit=60
```

This allows at most 60 requests per minute. Requests beyond the limit receive
an HTTP 429 (Too Many Requests) response.

### Disable rate limiting

```bash
juju config mcp-server rate-limit=0
```

## Command allowlist

The `command-allowlist` config restricts which executables the MCP server is
permitted to run when processing exec handlers. This provides defence in
depth -- even if a principal charm declares a tool, the server will refuse
to execute commands not on the allowlist.

### Set an allowlist

Provide a space-separated list of executable names:

```bash
juju config mcp-server command-allowlist="psql cat df ls"
```

With this configuration, only `psql`, `cat`, `df`, and `ls` may be invoked
by exec handlers. Any tool that tries to run a different command will fail.

### Allow all commands

Clear the config value to permit all commands (the default):

```bash
juju config mcp-server command-allowlist=""
```

## Recommended security configuration

For a production deployment, consider combining multiple layers:

```bash
# Use OAuth for authentication.
juju integrate mcp-server:oauth identity-provider:oauth

# Limit request rate.
juju config mcp-server rate-limit=120

# Restrict which commands can be executed.
juju config mcp-server command-allowlist="psql cat df uname"

# Enable TLS (see configure-tls.md).
juju integrate mcp-server:certificates self-signed-certificates:certificates
juju config mcp-server external-hostname="mcp.example.com"
```
