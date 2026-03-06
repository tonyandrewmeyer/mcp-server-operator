# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.

"""McpProvider — for charms that want to expose tools/prompts/resources via MCP."""

from __future__ import annotations

import dataclasses
import logging

import ops

from charmlibs.interfaces.mcp._models import McpDefinitions, Prompt, Resource, Tool

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class _McpRelationData:
    """Schema for data written to the relation app data bag."""

    mcp_definitions: str = ""


class McpProvider(ops.Object):
    """Manages the provider side of the ``mcp`` relation.

    The provider is typically a principal charm that wants to expose
    tools, prompts, and resources to an MCP server subordinate.

    Usage::

        class MyCharm(ops.CharmBase):
            def __init__(self, framework):
                super().__init__(framework)
                self.mcp = McpProvider(self, "mcp")
                framework.observe(self.on.mcp_relation_joined, self._on_mcp_joined)

            def _on_mcp_joined(self, event):
                self.mcp.set_definitions(McpDefinitions(tools=[...]))
    """

    def __init__(self, charm: ops.CharmBase, relation_name: str = "mcp"):
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name

    def set_definitions(self, definitions: McpDefinitions) -> None:
        """Publish MCP definitions on all current relations.

        This writes the definitions as a JSON string to the app data bag
        of every ``mcp`` relation.  Must be called by the leader unit.
        """
        if not self._charm.unit.is_leader():
            logger.debug("Not the leader; skipping set_definitions")
            return

        data = _McpRelationData(mcp_definitions=definitions.to_json())
        for relation in self._charm.model.relations.get(self._relation_name, []):
            relation.save(data, self._charm.app)
            logger.info(
                "Published MCP definitions on relation %d (%d tools, %d prompts, %d resources)",
                relation.id,
                len(definitions.tools),
                len(definitions.prompts),
                len(definitions.resources),
            )

    def set_tools(self, tools: list[Tool]) -> None:
        """Publish only tools, preserving any existing prompts and resources."""
        current = self._get_current_definitions()
        current.tools = tools
        self.set_definitions(current)

    def set_prompts(self, prompts: list[Prompt]) -> None:
        """Publish only prompts, preserving any existing tools and resources."""
        current = self._get_current_definitions()
        current.prompts = prompts
        self.set_definitions(current)

    def set_resources(self, resources: list[Resource]) -> None:
        """Publish only resources, preserving any existing tools and prompts."""
        current = self._get_current_definitions()
        current.resources = resources
        self.set_definitions(current)

    def _get_current_definitions(self) -> McpDefinitions:
        """Read the current definitions from the first relation, if any."""
        for relation in self._charm.model.relations.get(self._relation_name, []):
            data = relation.load(_McpRelationData, self._charm.app)
            if data.mcp_definitions:
                return McpDefinitions.from_json(data.mcp_definitions)
        return McpDefinitions()
