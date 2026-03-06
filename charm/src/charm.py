#!/usr/bin/env python3
# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.

"""MCP Server subordinate charm."""

from __future__ import annotations

import dataclasses
import json
import logging
import pathlib
from typing import Any

import ops
from charmlibs.interfaces.mcp import McpRequirer

import mcp_server

logger = logging.getLogger(__name__)

WORKLOAD_SERVER_SRC = pathlib.Path(__file__).parent / "workload_server.py"


@dataclasses.dataclass
class CharmConfig:
    """Typed charm configuration."""

    port: int = 8081
    log_level: str = "info"
    auth_token: str = ""
    rate_limit: int = 0
    command_allowlist: str = ""


class McpServerCharm(ops.CharmBase):
    """Subordinate charm that deploys an MCP server on the principal's machine."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        self.mcp = McpRequirer(self, "mcp")
        framework.observe(self.on.install, self._on_install)
        framework.observe(self.on.start, self._on_start)
        framework.observe(self.on.stop, self._on_stop)
        framework.observe(self.on.config_changed, self._on_config_changed)
        framework.observe(self.on.mcp_relation_changed, self._on_mcp_relation_changed)
        framework.observe(self.on.mcp_relation_broken, self._on_mcp_relation_broken)
        framework.observe(self.on.oauth_relation_changed, self._on_oauth_relation_changed)
        framework.observe(self.on.oauth_relation_broken, self._on_oauth_relation_broken)

    def _get_config(self) -> CharmConfig:
        """Load and return the typed charm configuration."""
        return self.load_config(CharmConfig, errors="blocked")

    def _get_oauth_config(self) -> dict[str, Any] | None:
        """Read OAuth provider info from the oauth relation, if available."""
        relation = self.model.get_relation("oauth")
        if not relation or not relation.app:
            return None
        data = relation.data[relation.app]
        issuer_url = data.get("issuer_url")
        if not issuer_url:
            return None

        oauth_config: dict[str, Any] = {
            "issuer_url": issuer_url,
            "resource_server_url": f"http://localhost:{self._get_config().port}",
        }
        if data.get("jwks_endpoint"):
            oauth_config["jwks_endpoint"] = data["jwks_endpoint"]
            oauth_config["jwks_uri"] = data["jwks_endpoint"]
        if data.get("introspection_endpoint"):
            oauth_config["introspection_endpoint"] = data["introspection_endpoint"]
        if data.get("client_id"):
            oauth_config["client_id"] = data["client_id"]
        # The client secret is stored as a Juju secret.
        client_secret_id = data.get("client_secret_id")
        if client_secret_id:
            secret = self.model.get_secret(id=client_secret_id)
            secret_content = secret.get_content()
            oauth_config["client_secret"] = secret_content.get("secret", "")
        if data.get("jwt_access_token"):
            oauth_config["jwt_access_token"] = json.loads(data["jwt_access_token"])
        return oauth_config

    def _write_systemd_unit(self) -> None:
        """Write the systemd unit with current config and OAuth settings."""
        config = self._get_config()
        mcp_server.write_systemd_unit(
            port=config.port,
            log_level=config.log_level,
            auth_token=config.auth_token,
            rate_limit=config.rate_limit,
            command_allowlist=config.command_allowlist,
            oauth_config=self._get_oauth_config(),
        )

    def _on_install(self, event: ops.InstallEvent) -> None:
        """Install the MCP server workload."""
        self.unit.status = ops.MaintenanceStatus("installing MCP server")
        mcp_server.install(WORKLOAD_SERVER_SRC)
        self._write_systemd_unit()

    def _on_start(self, event: ops.StartEvent) -> None:
        """Start the MCP server."""
        self.unit.status = ops.MaintenanceStatus("starting MCP server")
        if not self.mcp.has_definitions():
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
        """Handle config changes."""
        self._write_systemd_unit()
        if mcp_server.is_running():
            mcp_server.restart()

    def _on_mcp_relation_changed(self, event: ops.RelationChangedEvent) -> None:
        """Handle updates to MCP definitions from the principal charm."""
        self.unit.status = ops.MaintenanceStatus("configuring MCP server")
        definitions = self.mcp.collect_definitions()
        mcp_server.write_config(definitions)
        self._write_systemd_unit()

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

    def _on_oauth_relation_changed(self, event: ops.RelationChangedEvent) -> None:
        """Handle OAuth provider info arriving or changing."""
        self._write_systemd_unit()
        if mcp_server.is_running():
            mcp_server.restart()

    def _on_oauth_relation_broken(self, event: ops.RelationBrokenEvent) -> None:
        """Handle OAuth relation removal — fall back to simple auth or no auth."""
        self._write_systemd_unit()
        if mcp_server.is_running():
            mcp_server.restart()


if __name__ == "__main__":  # pragma: nocover
    ops.main(McpServerCharm)
