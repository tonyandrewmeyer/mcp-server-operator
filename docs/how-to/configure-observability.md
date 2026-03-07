# How to configure observability

This guide shows how to integrate the MCP server with the Canonical
Observability Stack (COS) for metrics, dashboards, alerting, tracing, and
log forwarding.

## Prerequisites

- A deployed `mcp-server` subordinate charm.
- The COS stack deployed (or the individual components you need).

## COS integration via grafana-agent

The MCP server charm provides a `cos-agent` relation that speaks the
`cos_agent` interface. This is the primary integration point for the full
Canonical Observability Stack.

### Deploy and relate grafana-agent

```bash
juju deploy grafana-agent
juju integrate mcp-server:cos-agent grafana-agent:cos-agent
```

The `cos-agent` relation automatically provides:

- **Metrics scrape targets** -- the Prometheus `/metrics` endpoint.
- **Grafana dashboard** -- a pre-built dashboard for MCP server metrics.
- **Prometheus alert rules** -- pre-configured alerting rules.

Grafana Agent collects these and forwards them to Prometheus, Grafana, and
Loki in the COS model.

## Prometheus metrics endpoint

The MCP server exposes a Prometheus-compatible metrics endpoint at `/metrics`
on its configured port (default 8081). If a `path-prefix` is set, the
metrics path is `/<prefix>/metrics`.

### Verify the metrics endpoint

```bash
curl http://<unit-address>:8081/metrics
```

Metrics include request counts, latencies, tool invocation counts, and error
rates.

### Manual scrape configuration

If you are not using the `cos-agent` relation, you can point any Prometheus
instance at the metrics endpoint directly. The port is configurable via:

```bash
juju config mcp-server port=9090
```

## Grafana dashboard

The charm ships a pre-built Grafana dashboard in
`charm/src/grafana_dashboards/mcp-server.json`. When the `cos-agent` relation
is active, this dashboard is automatically registered with Grafana via
grafana-agent.

The dashboard provides panels for:

- Request rate and latency
- Tool invocation counts and error rates
- Active connections
- Resource utilisation

No manual import is required when using the COS integration.

## Tracing via Tempo

The MCP server supports distributed tracing using OpenTelemetry. Traces are
exported via OTLP HTTP to a Tempo instance.

### Relate to a tracing provider

```bash
juju integrate mcp-server:charm-tracing tempo:tracing
```

The `charm-tracing` relation (interface: `tracing`) provides the OTLP HTTP
endpoint to the MCP server. Once related, the server sends trace spans for:

- Incoming MCP requests
- Tool handler executions (exec and HTTP)
- Outgoing HTTP calls

### Receiving CA certificates for tracing

If the Tempo endpoint uses TLS with a private CA, relate the CA certificate
provider so the MCP server trusts it:

```bash
juju integrate mcp-server:receive-ca-cert tempo:send-ca-cert
```

### Removing tracing

Breaking the relation disables trace export:

```bash
juju remove-relation mcp-server:charm-tracing tempo:tracing
```

## Log forwarding

The MCP server writes structured JSON logs to its systemd journal. This
makes logs straightforward to forward to Loki or any other log aggregation
system.

### Log format

All log lines are JSON objects with fields including:

- `timestamp` -- ISO 8601 timestamp.
- `level` -- Log level (info, debug, warning, error).
- `message` -- Human-readable log message.
- `logger` -- Logger name.

### Adjust log level

```bash
juju config mcp-server log-level="debug"
```

Acceptable values are `info`, `debug`, `warning`, and `error`.

### Forwarding to Loki

When grafana-agent is related via the `cos-agent` relation, it automatically
collects journal logs from the MCP server systemd unit and forwards them to
Loki. No additional configuration is required.

The charm also ships Loki alert rules alongside the Prometheus alert rules,
enabling log-based alerting in Grafana.

## Full COS integration example

To set up complete observability in a single sequence:

```bash
# Deploy the observability agents.
juju deploy grafana-agent
juju deploy tempo

# Relate the MCP server to observability.
juju integrate mcp-server:cos-agent grafana-agent:cos-agent
juju integrate mcp-server:charm-tracing tempo:tracing

# Optionally set debug logging for more detailed traces and logs.
juju config mcp-server log-level="debug"
```

This gives you metrics in Prometheus, dashboards in Grafana, traces in Tempo,
and logs in Loki -- all through the standard COS pipeline.
