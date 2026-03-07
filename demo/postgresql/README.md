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

- A Juju controller bootstrapped on a machine cloud.
- The `postgresql` charm deployed (provides the actual database server).
- The `mcp-server` subordinate charm available.

## Deployment

```bash
cd demo/postgresql
charmcraft pack

juju deploy ./postgresql-mcp_amd64.charm
juju integrate postgresql-mcp:mcp mcp-server:mcp
```

The `mcp-server` subordinate will attach to the `postgresql-mcp` unit and start
serving the declared tools over streamable HTTP.

## Example interactions

Once the MCP server is running, you can ask Claude Code (or any MCP client)
questions like:

- "List all databases on this PostgreSQL server."
- "Show me the largest tables in the **myapp** database."
- "Are there any slow queries running right now?"
- "Analyse the **myapp** database — check for missing indexes and table bloat."
- "Explain this query: `SELECT * FROM orders WHERE created_at > now() - interval '1 day'`"
- "Show me the current PostgreSQL configuration — anything unusual?"
- "Which authentication methods are configured in pg_hba.conf?"

## Safety note

Most of the tools execute read-only queries (`pg_stat_activity`,
`pg_settings`, `EXPLAIN ANALYZE`, and so on). However, the **run-query** tool
accepts arbitrary SQL and *could* execute writes or destructive statements.

A production deployment should use a dedicated read-only PostgreSQL role
instead of the `postgres` superuser. This demo uses `sudo -u postgres psql` for
simplicity.
