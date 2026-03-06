#!/usr/bin/env python3
# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.

"""Demo principal charm that provides MCP tools for testing."""

import logging

import ops

from charmlibs.mcp import (
    ExecHandler,
    McpDefinitions,
    McpProvider,
    Prompt,
    PromptArgument,
    Resource,
    Tool,
)

logger = logging.getLogger(__name__)

MCP_DEFINITIONS = McpDefinitions(
    tools=[
        Tool(
            name="system-info",
            description="Get basic system information (hostname, OS, uptime)",
            handler=ExecHandler(command=["uname", "-a"], timeout=10),
        ),
        Tool(
            name="disk-usage",
            description="Show disk usage for a given path",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Filesystem path to check",
                    },
                },
                "required": ["path"],
            },
            handler=ExecHandler(command=["df", "-h", "{{path}}"], timeout=10),
        ),
        Tool(
            name="list-files",
            description="List files in a directory",
            input_schema={
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory to list",
                    },
                },
                "required": ["directory"],
            },
            handler=ExecHandler(command=["ls", "-la", "{{directory}}"], timeout=10),
        ),
    ],
    prompts=[
        Prompt(
            name="diagnose-system",
            description="Diagnose system health and suggest improvements",
            template=(
                "Please diagnose the system health"
                "{% if focus %}, focusing on {{focus}}{% endif %}. "
                "Use the available tools to gather information, then provide "
                "a summary of findings and recommendations."
            ),
            arguments=[
                PromptArgument(
                    name="focus",
                    description="Area to focus on (disk, memory, network, general)",
                    required=False,
                ),
            ],
        ),
    ],
    resources=[
        Resource(
            uri="config://os-release",
            name="OS Release Info",
            description="Contents of /etc/os-release",
            handler=ExecHandler(command=["cat", "/etc/os-release"]),
        ),
    ],
)


class DemoPrincipalCharm(ops.CharmBase):
    """A minimal principal charm that provides MCP tool definitions."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        self.mcp = McpProvider(self, "mcp")
        framework.observe(self.on.start, self._on_start)
        framework.observe(self.on.mcp_relation_joined, self._on_mcp_relation_joined)

    def _on_start(self, event: ops.StartEvent) -> None:
        self.unit.status = ops.ActiveStatus()

    def _on_mcp_relation_joined(self, event: ops.RelationJoinedEvent) -> None:
        """Publish MCP definitions when the relation is established."""
        self.mcp.set_definitions(MCP_DEFINITIONS)


if __name__ == "__main__":  # pragma: nocover
    ops.main(DemoPrincipalCharm)
