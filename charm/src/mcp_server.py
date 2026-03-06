# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.

"""Functions for managing the MCP server workload on the local machine.

This module handles installing, configuring, starting, and stopping the MCP
server process via systemd. It is intentionally decoupled from charm concerns
so it could be used outside the context of a charm.
"""

from __future__ import annotations

import json
import logging
import pathlib
import subprocess
from typing import Any

logger = logging.getLogger(__name__)

CONFIG_DIR = pathlib.Path("/etc/mcp-server")
CONFIG_PATH = CONFIG_DIR / "config.json"
INSTALL_DIR = pathlib.Path("/opt/mcp-server")
VENV_DIR = INSTALL_DIR / "venv"
SERVICE_NAME = "mcp-server"
SYSTEMD_UNIT_PATH = pathlib.Path(f"/etc/systemd/system/{SERVICE_NAME}.service")

SYSTEMD_UNIT_TEMPLATE = """\
[Unit]
Description=MCP Server for Juju charms
After=network.target

[Service]
Type=simple
ExecStart={venv}/bin/python -m server \
    --config {config} \
    --host 0.0.0.0 \
    --port {port} \
    --log-level {log_level}{extra_args}
WorkingDirectory={install_dir}/src
Restart=on-failure
RestartSec=5
Environment=PYTHONPATH={install_dir}/src

[Install]
WantedBy=multi-user.target
"""


def install(server_src: pathlib.Path) -> None:
    """Install the MCP server workload.

    Creates a virtualenv, installs dependencies, and copies the server source.
    """
    logger.info("Installing MCP server workload")

    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # The base Ubuntu image does not include python3-venv.
    subprocess.run(
        ["/usr/bin/apt-get", "install", "-y", "python3-venv"],
        check=True,
    )

    subprocess.run(
        ["/usr/bin/python3", "-m", "venv", str(VENV_DIR)],
        check=True,
    )

    pip = str(VENV_DIR / "bin" / "pip")
    subprocess.run(
        [pip, "install", "mcp[cli]", "httpx", "PyJWT[crypto]"],
        check=True,
    )

    src_dest = INSTALL_DIR / "src"
    src_dest.mkdir(parents=True, exist_ok=True)
    if server_src.exists():
        (src_dest / "server.py").write_text(server_src.read_text())
    else:
        logger.warning("Server source not found at %s", server_src)

    # Copy the token verifier module alongside the server.
    token_verifier_src = server_src.parent / "token_verifier.py"
    if token_verifier_src.exists():
        (src_dest / "token_verifier.py").write_text(token_verifier_src.read_text())

    logger.info("MCP server installed to %s", INSTALL_DIR)


def write_config(definitions: dict[str, Any]) -> None:
    """Write MCP definitions to the config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(definitions, indent=2))
    logger.info("Wrote MCP config to %s", CONFIG_PATH)


def _oauth_extra_args(oauth_config: dict[str, Any]) -> str:
    """Build CLI args for OAuth configuration."""
    args = ""
    key_to_flag = {
        "issuer_url": "--oauth-issuer-url",
        "resource_server_url": "--oauth-resource-server-url",
        "jwks_uri": "--oauth-jwks-uri",
        "introspection_endpoint": "--oauth-introspection-endpoint",
        "client_id": "--oauth-client-id",
        "client_secret": "--oauth-client-secret",
    }
    for key, flag in key_to_flag.items():
        if oauth_config.get(key):
            args += f" \\\n    {flag} {oauth_config[key]}"
    if not oauth_config.get("jwt_access_token", True):
        args += " \\\n    --oauth-opaque-tokens"
    return args


def write_systemd_unit(
    port: int = 8081,
    log_level: str = "info",
    auth_token: str = "",
    rate_limit: int = 0,
    command_allowlist: str = "",
    oauth_config: dict[str, Any] | None = None,
) -> None:
    """Write the systemd unit file for the MCP server."""
    extra_args = ""
    if auth_token:
        extra_args += f" \\\n    --auth-token {auth_token}"
    if rate_limit > 0:
        extra_args += f" \\\n    --rate-limit {rate_limit}"
    if command_allowlist.strip():
        commands = command_allowlist.strip().split()
        extra_args += " \\\n    --command-allowlist " + " ".join(commands)
    if oauth_config:
        extra_args += _oauth_extra_args(oauth_config)

    unit_content = SYSTEMD_UNIT_TEMPLATE.format(
        venv=VENV_DIR,
        config=CONFIG_PATH,
        install_dir=INSTALL_DIR,
        port=port,
        log_level=log_level,
        extra_args=extra_args,
    )
    SYSTEMD_UNIT_PATH.write_text(unit_content)
    subprocess.run(
        ["/usr/bin/systemctl", "daemon-reload"],
        check=True,
    )
    logger.info("Wrote systemd unit to %s", SYSTEMD_UNIT_PATH)


def start() -> None:
    """Start (or restart) the MCP server service."""
    subprocess.run(
        ["/usr/bin/systemctl", "enable", "--now", SERVICE_NAME],
        check=True,
    )
    logger.info("MCP server started")


def restart() -> None:
    """Restart the MCP server service."""
    subprocess.run(
        ["/usr/bin/systemctl", "restart", SERVICE_NAME],
        check=True,
    )
    logger.info("MCP server restarted")


def stop() -> None:
    """Stop the MCP server service."""
    subprocess.run(
        ["/usr/bin/systemctl", "stop", SERVICE_NAME],
        check=False,
    )
    logger.info("MCP server stopped")


def is_running() -> bool:
    """Check if the MCP server service is running."""
    result = subprocess.run(
        ["/usr/bin/systemctl", "is-active", "--quiet", SERVICE_NAME],
        check=False,
    )
    return result.returncode == 0


def get_version() -> str | None:
    """Get the version of the MCP server."""
    try:
        result = subprocess.run(
            [str(VENV_DIR / "bin" / "pip"), "show", "mcp"],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.splitlines():
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None
