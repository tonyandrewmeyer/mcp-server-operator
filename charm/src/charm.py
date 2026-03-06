#!/usr/bin/env python3
# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.

"""MCP Server subordinate charm."""

from __future__ import annotations

import dataclasses
import json
import logging
import pathlib

import ops

import mcp_server

logger = logging.getLogger(__name__)

WORKLOAD_SERVER_SRC = pathlib.Path(__file__).parent / "workload_server.py"


@dataclasses.dataclass
class CharmConfig:
    """Typed charm configuration."""

    port: int = 8081
    log_level: str = "info"


@dataclasses.dataclass
class McpRelationData:
    """Data provided by the principal charm on the mcp relation.

    The mcp_definitions field is automatically deserialised from JSON by
    ``relation.load()``, so it arrives as a dict rather than a raw string.
    """

    mcp_definitions: dict | str = dataclasses.field(default_factory=dict)


class McpServerCharm(ops.CharmBase):
    """Subordinate charm that deploys an MCP server on the principal's machine."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        framework.observe(self.on.install, self._on_install)
        framework.observe(self.on.start, self._on_start)
        framework.observe(self.on.stop, self._on_stop)
        framework.observe(self.on.config_changed, self._on_config_changed)
        framework.observe(self.on.mcp_relation_changed, self._on_mcp_relation_changed)
        framework.observe(self.on.mcp_relation_broken, self._on_mcp_relation_broken)

    def _get_config(self) -> CharmConfig:
        """Load and return the typed charm configuration."""
        return self.load_config(CharmConfig, errors="blocked")

    def _on_install(self, event: ops.InstallEvent) -> None:
        """Install the MCP server workload."""
        self.unit.status = ops.MaintenanceStatus("installing MCP server")
        mcp_server.install(WORKLOAD_SERVER_SRC)
        config = self._get_config()
        mcp_server.write_systemd_unit(port=config.port, log_level=config.log_level)

    def _on_start(self, event: ops.StartEvent) -> None:
        """Start the MCP server."""
        self.unit.status = ops.MaintenanceStatus("starting MCP server")
        if not self._has_mcp_definitions():
            self.unit.status = ops.WaitingStatus("waiting for mcp relation data")
            return
        mcp_server.start()
        version = mcp_server.get_version()
        if version is not None:
            self.unit.set_workload_version(version)
        self.unit.status = ops.ActiveStatus()

    def _on_stop(self, event: ops.StopEvent) -> None:
        """Stop the MCP server."""
        mcp_server.stop()

    def _on_config_changed(self, event: ops.ConfigChangedEvent) -> None:
        """Handle config changes (port, log-level)."""
        config = self._get_config()
        mcp_server.write_systemd_unit(port=config.port, log_level=config.log_level)
        if mcp_server.is_running():
            mcp_server.restart()

    def _on_mcp_relation_changed(self, event: ops.RelationChangedEvent) -> None:
        """Handle updates to MCP definitions from the principal charm."""
        self.unit.status = ops.MaintenanceStatus("configuring MCP server")
        definitions = self._collect_mcp_definitions()
        mcp_server.write_config(definitions)

        config = self._get_config()
        mcp_server.write_systemd_unit(port=config.port, log_level=config.log_level)

        if mcp_server.is_running():
            mcp_server.restart()
        else:
            mcp_server.start()

        version = mcp_server.get_version()
        if version is not None:
            self.unit.set_workload_version(version)
        self.unit.status = ops.ActiveStatus()

    def _on_mcp_relation_broken(self, event: ops.RelationBrokenEvent) -> None:
        """Handle the mcp relation being removed."""
        mcp_server.write_config({"tools": [], "prompts": [], "resources": []})
        mcp_server.stop()
        self.unit.status = ops.BlockedStatus("no mcp relation")

    def _has_mcp_definitions(self) -> bool:
        """Check if any mcp relation has provided definitions."""
        for relation in self.model.relations.get("mcp", []):
            remote_app = relation.app
            if not remote_app:
                continue
            data = relation.load(McpRelationData, remote_app)
            if data.mcp_definitions:
                return True
        return False

    def _collect_mcp_definitions(self) -> dict:
        """Collect and merge MCP definitions from all mcp relations."""
        all_tools: list = []
        all_prompts: list = []
        all_resources: list = []

        for relation in self.model.relations.get("mcp", []):
            remote_app = relation.app
            if not remote_app:
                continue
            data = relation.load(McpRelationData, remote_app)
            if not data.mcp_definitions:
                continue
            # relation.load() deserialises JSON values automatically, so
            # mcp_definitions is normally a dict.  Handle a raw string as
            # a fallback for forward-compatibility.
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


if __name__ == "__main__":  # pragma: nocover
    ops.main(McpServerCharm)
