#!/usr/bin/env python3
# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.

"""MCP Server subordinate charm."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import ops

import mcp_server

logger = logging.getLogger(__name__)

# The workload server source is bundled alongside the charm code in src/.
WORKLOAD_SERVER_SRC = Path(__file__).parent / "workload_server.py"


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

    def _on_install(self, event: ops.InstallEvent) -> None:
        """Install the MCP server workload."""
        self.unit.status = ops.MaintenanceStatus("installing MCP server")
        mcp_server.install(WORKLOAD_SERVER_SRC)
        port = int(self.config.get("port", 8081))
        log_level = str(self.config.get("log-level", "info"))
        mcp_server.write_systemd_unit(port=port, log_level=log_level)

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
        port = int(self.config.get("port", 8081))
        log_level = str(self.config.get("log-level", "info"))
        mcp_server.write_systemd_unit(port=port, log_level=log_level)
        if mcp_server.is_running():
            mcp_server.restart()

    def _on_mcp_relation_changed(self, event: ops.RelationChangedEvent) -> None:
        """Handle updates to MCP definitions from the principal charm."""
        self.unit.status = ops.MaintenanceStatus("configuring MCP server")
        definitions = self._collect_mcp_definitions()
        mcp_server.write_config(definitions)

        port = int(self.config.get("port", 8081))
        log_level = str(self.config.get("log-level", "info"))
        mcp_server.write_systemd_unit(port=port, log_level=log_level)

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
        # Write empty config and stop the server.
        mcp_server.write_config({"tools": [], "prompts": [], "resources": []})
        mcp_server.stop()
        self.unit.status = ops.BlockedStatus("no mcp relation")

    def _has_mcp_definitions(self) -> bool:
        """Check if any mcp relation has provided definitions."""
        for relation in self.model.relations.get("mcp", []):
            remote_app = relation.app
            if remote_app and relation.data.get(remote_app, {}).get("mcp_definitions"):
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
            raw = relation.data.get(remote_app, {}).get("mcp_definitions", "")
            if not raw:
                continue
            try:
                definitions = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning(
                    "Invalid JSON in mcp_definitions from %s (relation %d)",
                    remote_app.name,
                    relation.id,
                )
                continue

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
