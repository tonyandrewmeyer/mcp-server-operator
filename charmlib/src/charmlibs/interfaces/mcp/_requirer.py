# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.

"""McpRequirer — for the mcp-server charm to read relation data."""

from __future__ import annotations

import dataclasses
import json
import logging
from typing import Any

import ops

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class _McpRelationData:
    """Schema for data on the relation app data bag."""

    mcp_definitions: dict = dataclasses.field(default_factory=dict)


class McpRequirer(ops.Object):
    """Manages the requirer side of the ``mcp`` relation.

    The requirer is typically the mcp-server subordinate charm that reads
    tool/prompt/resource definitions from all related provider charms.

    Usage::

        class McpServerCharm(ops.CharmBase):
            def __init__(self, framework):
                super().__init__(framework)
                self.mcp = McpRequirer(self, "mcp")

            def _on_relation_changed(self, event):
                definitions = self.mcp.collect_definitions()
                # definitions is a merged dict with keys: tools, prompts, resources
    """

    def __init__(self, charm: ops.CharmBase, relation_name: str = "mcp"):
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name

    def has_definitions(self) -> bool:
        """Return True if any related provider has published definitions."""
        for relation in self._charm.model.relations.get(self._relation_name, []):
            remote_app = relation.app
            if not remote_app:
                continue
            data = relation.load(_McpRelationData, remote_app)
            if data.mcp_definitions:
                return True
        return False

    def collect_definitions(self) -> dict[str, Any]:
        """Collect and merge MCP definitions from all related providers.

        Returns a dict with keys ``tools``, ``prompts``, and ``resources``,
        each containing a list of definition dicts merged from every
        provider relation.
        """
        all_tools: list[dict[str, Any]] = []
        all_prompts: list[dict[str, Any]] = []
        all_resources: list[dict[str, Any]] = []

        for relation in self._charm.model.relations.get(self._relation_name, []):
            remote_app = relation.app
            if not remote_app:
                continue
            data = relation.load(_McpRelationData, remote_app)
            if not data.mcp_definitions:
                continue

            # relation.load() deserialises JSON values automatically, so
            # mcp_definitions is normally a dict.  Handle a raw string as
            # a fallback.
            if isinstance(data.mcp_definitions, str):
                try:
                    definitions = json.loads(data.mcp_definitions)
                except json.JSONDecodeError:
                    logger.warning(
                        "Invalid JSON in mcp_definitions from %s (relation %d)",
                        remote_app.name,
                        relation.id,
                    )
                    continue
            else:
                definitions = data.mcp_definitions

            all_tools.extend(definitions.get("tools", []))
            all_prompts.extend(definitions.get("prompts", []))
            all_resources.extend(definitions.get("resources", []))

        return {
            "tools": all_tools,
            "prompts": all_prompts,
            "resources": all_resources,
        }
