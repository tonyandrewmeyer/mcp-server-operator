# How to configure TLS

This guide shows how to enable TLS encryption for the MCP server, either
directly via a certificates relation or through a TLS-terminating reverse
proxy.

## Prerequisites

- A deployed `mcp-server` subordinate charm.

## Option 1: Direct TLS via the certificates relation

The MCP server charm has a `certificates` relation that speaks the
`tls-certificates` interface. When a certificate provider supplies a
certificate and private key, the MCP server automatically enables HTTPS.

### Deploy a certificate provider and relate

Any charm that provides the `tls-certificates` interface will work. For
example, using a self-signed certificates operator:

```bash
juju deploy self-signed-certificates
juju integrate mcp-server:certificates self-signed-certificates:certificates
```

### Set the external hostname

When using the certificates relation, set the `external-hostname` config to
the FQDN that clients use to reach the MCP server. This hostname is used
when requesting the TLS certificate:

```bash
juju config mcp-server external-hostname="mcp.example.com"
```

### How it works

Once the relation is established and a certificate is issued:

1. The charm writes the certificate, private key, and CA chain to
   `/etc/mcp-server/tls/`.
2. The systemd unit is updated to pass `--tls-cert` and `--tls-key` flags to
   the server process.
3. The server restarts and begins serving on HTTPS.

### Removing TLS

Breaking the certificates relation removes the TLS files and restarts the
server on plain HTTP:

```bash
juju remove-relation mcp-server:certificates self-signed-certificates:certificates
```

## Option 2: TLS via reverse proxy

When HAProxy (or another reverse proxy) handles TLS termination, the MCP
server itself runs on plain HTTP. This is often simpler to manage because the
certificate lifecycle is handled by the proxy.

### Deploy HAProxy with TLS

```bash
juju deploy haproxy
juju integrate mcp-server:reverse-proxy haproxy:reverseproxy
juju integrate haproxy:certificates self-signed-certificates:certificates
```

In this setup:

- Clients connect to HAProxy over HTTPS.
- HAProxy terminates TLS and forwards traffic to the MCP server over HTTP.
- The MCP server does not need its own certificate.

### When to use each option

| Approach              | Use when                                                  |
|-----------------------|-----------------------------------------------------------|
| Direct TLS            | The MCP server is accessed directly without a proxy.      |
| TLS via reverse proxy | You already have HAProxy in front of the MCP server.      |

Avoid enabling both simultaneously -- if HAProxy is handling TLS, the MCP
server should remain on plain HTTP to avoid double encryption.

## Receiving CA certificates

The MCP server charm also has a `receive-ca-cert` relation (interface:
`certificate_transfer`) that accepts CA certificates from other charms. This
is useful when the MCP server needs to trust a private CA -- for example,
when making HTTP handler calls to a principal workload that uses internal TLS:

```bash
juju integrate mcp-server:receive-ca-cert my-ca-provider:send-ca-cert
```
