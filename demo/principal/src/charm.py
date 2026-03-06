#!/usr/bin/env python3
# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.

"""Demo principal charm that provides MCP tools for testing."""

import json
import logging

import ops

logger = logging.getLogger(__name__)

MCP_DEFINITIONS = {
    "tools": [
        {
            "name": "system-info",
            "description": "Get basic system information (hostname, OS, uptime)",
            "input_schema": {"type": "object", "properties": {}, "required": []},
            "handler": {
                "type": "exec",
                "command": ["uname", "-a"],
                "timeout": 10,
            },
        },
        {
            "name": "disk-usage",
            "description": "Show disk usage for a given path",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Filesystem path to check",
                    },
                },
                "required": ["path"],
            },
            "handler": {
                "type": "exec",
                "command": ["df", "-h", "{{path}}"],
                "timeout": 10,
            },
        },
        {
            "name": "list-files",
            "description": "List files in a directory",
            "input_schema": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory to list",
                    },
                },
                "required": ["directory"],
            },
            "handler": {
                "type": "exec",
                "command": ["ls", "-la", "{{directory}}"],
                "timeout": 10,
            },
        },
    ],
    "prompts": [
        {
            "name": "diagnose-system",
            "description": "Diagnose system health and suggest improvements",
            "arguments": [
                {
                    "name": "focus",
                    "description": "Area to focus on (disk, memory, network, general)",
                    "required": False,
                },
            ],
            "template": (
                "Please diagnose the system health"
                "{% if focus %}, focusing on {{focus}}{% endif %}. "
                "Use the available tools to gather information, then provide "
                "a summary of findings and recommendations."
            ),
        },
    ],
    "resources": [
        {
            "uri": "config://os-release",
            "name": "OS Release Info",
            "description": "Contents of /etc/os-release",
            "mime_type": "text/plain",
            "handler": {
                "type": "exec",
                "command": ["cat", "/etc/os-release"],
            },
        },
    ],
}


class DemoPrincipalCharm(ops.CharmBase):
    """A minimal principal charm that provides MCP tool definitions."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        framework.observe(self.on.start, self._on_start)
        framework.observe(self.on.mcp_relation_joined, self._on_mcp_relation_joined)

    def _on_start(self, event: ops.StartEvent) -> None:
        self.unit.status = ops.ActiveStatus()

    def _on_mcp_relation_joined(self, event: ops.RelationJoinedEvent) -> None:
        """Publish MCP definitions when the relation is established."""
        event.relation.data[self.app]["mcp_definitions"] = json.dumps(MCP_DEFINITIONS)
        logger.info("Published MCP definitions on relation %d", event.relation.id)


if __name__ == "__main__":  # pragma: nocover
    ops.main(DemoPrincipalCharm)
