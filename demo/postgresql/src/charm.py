#!/usr/bin/env python3
# Copyright 2026 Ubuntu
# See LICENSE file for licensing details.

"""PostgreSQL MCP demo charm — exposes PostgreSQL tools, prompts, and resources via MCP."""

import logging

import ops

from charmlibs.interfaces import mcp

logger = logging.getLogger(__name__)

# SQL fragments used in tool commands, kept here for readability.
_TABLE_SIZES_SQL = (
    "SELECT schemaname, tablename,"
    " pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) AS size"
    " FROM pg_tables"
    " WHERE schemaname NOT IN ('pg_catalog', 'information_schema')"
    " ORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC;"
)

_ACTIVE_CONNECTIONS_SQL = (
    "SELECT pid, usename, datname, client_addr, state, query_start, query"
    " FROM pg_stat_activity"
    " WHERE state != 'idle'"
    " ORDER BY query_start;"
)

_LIST_INDEXES_SQL = (
    "SELECT schemaname, tablename, indexname,"
    " pg_size_pretty(pg_relation_size(indexrelid)) AS size"
    " FROM pg_stat_user_indexes"
    " ORDER BY pg_relation_size(indexrelid) DESC;"
)

_NON_DEFAULT_SETTINGS_SQL = (
    "SELECT name, setting, short_desc"
    " FROM pg_settings"
    " WHERE source != 'default'"
    " ORDER BY name;"
)

_HBA_RULES_SQL = (
    "SELECT line_number, type, database, user_name, address, auth_method"
    " FROM pg_hba_file_rules"
    " ORDER BY line_number;"
)

MCP_DEFINITIONS = mcp.McpDefinitions(
    tools=[
        mcp.Tool(
            name="list-databases",
            description="List all PostgreSQL databases on this server",
            handler=mcp.ExecHandler(
                command=["sudo", "-u", "postgres", "psql", "-l", "--csv"],
                timeout=10,
            ),
        ),
        mcp.Tool(
            name="run-query",
            description="Run an arbitrary SQL query against a named database (returns CSV)",
            input_schema={
                "type": "object",
                "properties": {
                    "database": {
                        "type": "string",
                        "description": "Name of the PostgreSQL database",
                    },
                    "query": {
                        "type": "string",
                        "description": "SQL query to execute",
                    },
                },
                "required": ["database", "query"],
            },
            handler=mcp.ExecHandler(
                command=[
                    "sudo", "-u", "postgres", "psql",
                    "-d", "{{database}}",
                    "-c", "{{query}}",
                    "--csv",
                ],
                timeout=30,
            ),
        ),
        mcp.Tool(
            name="table-sizes",
            description="Show all user tables ordered by total size (descending)",
            input_schema={
                "type": "object",
                "properties": {
                    "database": {
                        "type": "string",
                        "description": "Name of the PostgreSQL database",
                    },
                },
                "required": ["database"],
            },
            handler=mcp.ExecHandler(
                command=[
                    "sudo", "-u", "postgres", "psql",
                    "-d", "{{database}}",
                    "-c", _TABLE_SIZES_SQL,
                    "--csv",
                ],
                timeout=15,
            ),
        ),
        mcp.Tool(
            name="active-connections",
            description="Show all non-idle connections with their current queries",
            handler=mcp.ExecHandler(
                command=[
                    "sudo", "-u", "postgres", "psql",
                    "-c", _ACTIVE_CONNECTIONS_SQL,
                    "--csv",
                ],
                timeout=10,
            ),
        ),
        mcp.Tool(
            name="explain-query",
            description="Run EXPLAIN ANALYZE on a query to show its execution plan",
            input_schema={
                "type": "object",
                "properties": {
                    "database": {
                        "type": "string",
                        "description": "Name of the PostgreSQL database",
                    },
                    "query": {
                        "type": "string",
                        "description": "SQL query to explain",
                    },
                },
                "required": ["database", "query"],
            },
            handler=mcp.ExecHandler(
                command=[
                    "sudo", "-u", "postgres", "psql",
                    "-d", "{{database}}",
                    "-c", "EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) {{query}}",
                    "--csv",
                ],
                timeout=60,
            ),
        ),
        mcp.Tool(
            name="list-indexes",
            description="List all user indexes ordered by size (descending)",
            input_schema={
                "type": "object",
                "properties": {
                    "database": {
                        "type": "string",
                        "description": "Name of the PostgreSQL database",
                    },
                },
                "required": ["database"],
            },
            handler=mcp.ExecHandler(
                command=[
                    "sudo", "-u", "postgres", "psql",
                    "-d", "{{database}}",
                    "-c", _LIST_INDEXES_SQL,
                    "--csv",
                ],
                timeout=15,
            ),
        ),
    ],
    prompts=[
        mcp.Prompt(
            name="analyse-database",
            description="Analyse the overall health of a PostgreSQL database",
            template=(
                "Please analyse the health of the {{database}} database. "
                "Check the table sizes and look for unexpectedly large tables. "
                "Review the indexes — identify any missing indexes or unused ones. "
                "Look at active connections for anything unusual. "
                "Summarise the overall health and flag any concerns such as "
                "table bloat, missing indexes, or connection pressure."
            ),
            arguments=[
                mcp.PromptArgument(
                    name="database",
                    description="Name of the PostgreSQL database to analyse",
                    required=True,
                ),
            ],
        ),
        mcp.Prompt(
            name="diagnose-performance",
            description="Diagnose performance issues in a PostgreSQL database",
            template=(
                "Please diagnose performance issues in the {{database}} database. "
                "Check for slow or long-running queries using active connections. "
                "Look for missing indexes by examining table sizes versus index coverage. "
                "Review connection counts for potential exhaustion. "
                "Use EXPLAIN ANALYZE on any suspicious queries you find. "
                "Provide concrete recommendations to improve performance."
            ),
            arguments=[
                mcp.PromptArgument(
                    name="database",
                    description="Name of the PostgreSQL database to diagnose",
                    required=True,
                ),
            ],
        ),
    ],
    resources=[
        mcp.Resource(
            uri="config://postgresql/main",
            name="PostgreSQL Configuration",
            description="All non-default PostgreSQL settings (from pg_settings)",
            handler=mcp.ExecHandler(
                command=[
                    "sudo", "-u", "postgres", "psql",
                    "-c", _NON_DEFAULT_SETTINGS_SQL,
                    "--csv",
                ],
            ),
        ),
        mcp.Resource(
            uri="config://postgresql/hba",
            name="PostgreSQL HBA Rules",
            description="Client authentication rules (from pg_hba_file_rules)",
            handler=mcp.ExecHandler(
                command=[
                    "sudo", "-u", "postgres", "psql",
                    "-c", _HBA_RULES_SQL,
                    "--csv",
                ],
            ),
        ),
    ],
)


class PostgresqlMcpCharm(ops.CharmBase):
    """Principal charm that exposes PostgreSQL databases via MCP tools."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        self.mcp = mcp.McpProvider(self, "mcp")
        framework.observe(self.on.start, self._on_start)
        framework.observe(self.on.mcp_relation_joined, self._on_mcp_relation_joined)

    def _on_start(self, event: ops.StartEvent) -> None:
        self.unit.status = ops.ActiveStatus()

    def _on_mcp_relation_joined(self, event: ops.RelationJoinedEvent) -> None:
        """Publish MCP definitions when the relation is established."""
        self.mcp.set_definitions(MCP_DEFINITIONS)


if __name__ == "__main__":  # pragma: nocover
    ops.main(PostgresqlMcpCharm)
