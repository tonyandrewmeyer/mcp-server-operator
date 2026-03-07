# PostgreSQL MCP Demo

A demo principal charm that exposes PostgreSQL databases via the MCP protocol.
Once deployed alongside the `mcp-server` subordinate, LLM agents (such as
Claude Code) can list databases, run queries, inspect indexes, analyse
performance, and review server configuration — all through natural language.

## What this demonstrates

- Six MCP **tools** that query a real PostgreSQL server: list databases, run
  arbitrary SQL, show table sizes, view active connections, explain query plans,
  and list indexes.
- Two MCP **prompts** that guide an LLM through structured database analysis
  and performance diagnosis workflows.
- Two MCP **resources** that expose the live PostgreSQL configuration and
  client authentication (HBA) rules.

## Prerequisites

- A Juju controller bootstrapped on a machine cloud (e.g. LXD).
- The `mcp-server` subordinate charm packed (`cd charm && charmcraft pack`).

## Deployment

```bash
# Pack both charms.
cd demo/postgresql && charmcraft pack
cd charm && charmcraft pack  # if not already packed

# Create a model and deploy PostgreSQL.
juju add-model pg-demo
juju deploy postgresql --channel 14/stable

# Wait for PostgreSQL to become active.
juju wait-for application postgresql --timeout 300s

# Deploy postgresql-mcp on the same machine as PostgreSQL.
juju deploy ./demo/postgresql/postgresql-mcp_amd64.charm postgresql-mcp \
  --to $(juju status --format json | jq -r '.applications.postgresql.units | to_entries[0].value.machine')

# Deploy mcp-server (subordinate — it will land on postgresql-mcp's machine).
juju deploy ./charm/mcp-server_amd64.charm mcp-server

# Wire them up.
juju integrate postgresql-mcp:mcp mcp-server:mcp

# Wait for everything to settle.
juju wait-for application mcp-server --timeout 120s
```

> **Note:** The `postgresql` charm (charmed-postgresql snap) uses
> `ubuntu@22.04`. Both `postgresql-mcp` and `mcp-server` must target the same
> base to be co-located on the same machine. If you get a base mismatch error,
> update `charmcraft.yaml` to use `base: ubuntu@22.04` and re-pack.

## Verify

```bash
# Get the machine IP.
IP=$(juju status --format json | jq -r '.applications.postgresql.units | to_entries[0].value["public-address"]')

# List databases.
curl -s http://$IP:8081/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list-databases","arguments":{}}}'

# Run a query.
curl -s http://$IP:8081/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"run-query","arguments":{"database":"postgres","query":"SELECT version();"}}}'

# Show active connections.
curl -s http://$IP:8081/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"active-connections","arguments":{}}}'
```

## Connect Claude Code

Add the MCP server to your Claude Code configuration:

```json
{
  "mcpServers": {
    "postgresql": {
      "type": "streamable-http",
      "url": "http://<IP>:8081/mcp"
    }
  }
}
```

Then ask Claude things like:

- "List all databases on this PostgreSQL server."
- "Create a test database and add some sample tables."
- "Show me the largest tables in testdb."
- "Are there any slow queries running right now?"
- "Analyse the testdb database — check for missing indexes and table bloat."
- "Explain this query: `SELECT u.name, COUNT(o.id) FROM users u JOIN orders o ON u.id = o.user_id GROUP BY u.name ORDER BY COUNT(o.id) DESC LIMIT 10;`"
- "Show me the current PostgreSQL configuration — anything unusual?"
- "Which authentication methods are configured in pg_hba.conf?"

## Safety note

Most of the tools execute read-only queries (`pg_stat_activity`,
`pg_settings`, `EXPLAIN ANALYZE`, and so on). However, the **run-query** tool
accepts arbitrary SQL and *could* execute writes or destructive statements.

The demo uses the `backup` database role (which has broad privileges on the
charmed-postgresql snap). A production deployment should use a dedicated
read-only PostgreSQL role with tightly scoped permissions. You can also use the
`command-allowlist` config option on the `mcp-server` charm to restrict which
commands are allowed.
