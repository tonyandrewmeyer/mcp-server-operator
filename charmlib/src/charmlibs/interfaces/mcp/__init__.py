# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.

"""Charm library for the MCP (Model Context Protocol) Juju interface.

This library provides :class:`McpProvider` and :class:`McpRequirer` classes
that charm authors can use to integrate with the ``mcp`` relation interface.

A **provider** (typically a principal charm) declares tools, prompts, and
resources that it wants to expose via MCP::

    from charmlibs.interfaces.mcp import McpProvider, Tool, ExecHandler

    class MyCharm(ops.CharmBase):
        def __init__(self, framework):
            super().__init__(framework)
            self.mcp = McpProvider(self, "mcp")
            self.mcp.set_tools([
                Tool(
                    name="list-files",
                    description="List files in a directory",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "dir": {"type": "string", "description": "Directory"},
                        },
                        "required": ["dir"],
                    },
                    handler=ExecHandler(command=["ls", "-la", "{{dir}}"]),
                ),
            ])

A **requirer** (the mcp-server subordinate charm) reads and merges
definitions from all related providers::

    from charmlibs.interfaces.mcp import McpRequirer

    class McpServerCharm(ops.CharmBase):
        def __init__(self, framework):
            super().__init__(framework)
            self.mcp = McpRequirer(self, "mcp")

        def _on_relation_changed(self, event):
            definitions = self.mcp.collect_definitions()
"""

from charmlibs.interfaces.mcp._models import (
    ExecHandler,
    HttpHandler,
    McpDefinitions,
    Prompt,
    PromptArgument,
    Resource,
    Tool,
)
from charmlibs.interfaces.mcp._provider import McpProvider
from charmlibs.interfaces.mcp._requirer import McpRequirer

__all__ = [
    "ExecHandler",
    "HttpHandler",
    "McpDefinitions",
    "McpProvider",
    "McpRequirer",
    "Prompt",
    "PromptArgument",
    "Resource",
    "Tool",
]
