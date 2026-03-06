# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.

"""MCP server that dynamically serves tools, prompts, and resources from a JSON config file.

The server reads declarations from a JSON config file and exposes them via
streamable HTTP. Tool/resource handlers execute shell commands or HTTP requests
as declared in the config.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent

logger = logging.getLogger(__name__)

# Pattern for {{placeholder}} template substitution.
TEMPLATE_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def substitute_template(template: str, arguments: dict[str, Any]) -> str:
    """Replace {{param}} placeholders with argument values."""

    def replacer(match: re.Match) -> str:
        key = match.group(1)
        if key not in arguments:
            raise ValueError(f"Missing required argument: {key}")
        return str(arguments[key])

    return TEMPLATE_PATTERN.sub(replacer, template)


def substitute_command(command: list[str], arguments: dict[str, Any]) -> list[str]:
    """Substitute templates in a command argv list.

    Each element is substituted independently, preserving argv boundaries
    to prevent shell injection.
    """
    return [substitute_template(arg, arguments) for arg in command]


def execute_exec_handler(handler: dict[str, Any], arguments: dict[str, Any]) -> str:
    """Execute an exec-type handler and return its stdout."""
    command = substitute_command(handler["command"], arguments)
    timeout = handler.get("timeout", 60)
    user = handler.get("user")
    working_dir = handler.get("working_dir")
    env = handler.get("env")

    if user:
        command = ["sudo", "-u", user, "--"] + command

    result = subprocess.run(  # noqa: S603
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=working_dir,
        env=env,
    )

    if result.returncode != 0:
        return f"Command failed (exit code {result.returncode}):\n{result.stderr}"

    return result.stdout


async def execute_http_handler(handler: dict[str, Any], arguments: dict[str, Any]) -> str:
    """Execute an http-type handler and return the response body."""
    url = substitute_template(handler["url"], arguments)
    method = handler.get("method", "GET").upper()
    timeout = handler.get("timeout", 30)
    headers = handler.get("headers", {})

    body = None
    if "body_template" in handler:
        body = substitute_template(handler["body_template"], arguments)

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method,
            url,
            headers=headers,
            content=body,
            timeout=timeout,
        )
        return response.text


def load_config(config_path: Path) -> dict[str, Any]:
    """Load and return the MCP definitions config file."""
    if not config_path.exists():
        logger.warning("Config file %s does not exist, using empty config", config_path)
        return {"tools": [], "prompts": [], "resources": []}

    with open(config_path) as f:
        config = json.load(f)

    config.setdefault("tools", [])
    config.setdefault("prompts", [])
    config.setdefault("resources", [])
    return config


def register_tool(mcp: FastMCP, tool_def: dict[str, Any]) -> None:
    """Register a single tool definition with the MCP server."""
    name = tool_def["name"]
    description = tool_def["description"]
    input_schema = tool_def.get("input_schema", {})
    handler = tool_def["handler"]

    # Extract parameter names and build the function signature info for FastMCP.
    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))

    async def tool_handler(**kwargs: Any) -> list[TextContent]:
        handler_type = handler["type"]
        if handler_type == "exec":
            output = execute_exec_handler(handler, kwargs)
        elif handler_type == "http":
            output = await execute_http_handler(handler, kwargs)
        else:
            output = f"Unknown handler type: {handler_type}"
        return [TextContent(type="text", text=output)]

    # Build parameter descriptions for FastMCP.
    param_descriptions = {}
    for param_name, param_def in properties.items():
        if "description" in param_def:
            param_descriptions[param_name] = param_def["description"]

    # Register with FastMCP using add_tool for dynamic registration.
    # We wrap our handler to match FastMCP's expectations.
    mcp.add_tool(
        tool_handler,
        name=name,
        description=description,
    )

    logger.info(
        "Registered tool: %s (%d params, %d required)",
        name,
        len(properties),
        len(required),
    )


def register_prompt(mcp: FastMCP, prompt_def: dict[str, Any]) -> None:
    """Register a single prompt definition with the MCP server."""
    name = prompt_def["name"]
    description = prompt_def["description"]
    template = prompt_def["template"]

    async def prompt_handler(**kwargs: Any) -> str:
        return substitute_template(template, kwargs)

    mcp.add_prompt(prompt_handler, name=name, description=description)
    logger.info("Registered prompt: %s", name)


def register_resource(mcp: FastMCP, resource_def: dict[str, Any]) -> None:
    """Register a single resource definition with the MCP server."""
    uri = resource_def["uri"]
    name = resource_def["name"]
    description = resource_def["description"]
    handler = resource_def["handler"]
    mime_type = resource_def.get("mime_type", "text/plain")

    async def resource_handler() -> str:
        handler_type = handler["type"]
        if handler_type == "exec":
            return execute_exec_handler(handler, {})
        elif handler_type == "http":
            return await execute_http_handler(handler, {})
        else:
            return f"Unknown handler type: {handler_type}"

    mcp.add_resource(
        resource_handler,
        uri=uri,
        name=name,
        description=description,
        mime_type=mime_type,
    )
    logger.info("Registered resource: %s (%s)", name, uri)


def create_server(config_path: Path) -> FastMCP:
    """Create and configure an MCP server from a config file."""
    config = load_config(config_path)

    mcp = FastMCP("mcp-server-charm", stateless_http=True)

    for tool_def in config["tools"]:
        register_tool(mcp, tool_def)

    for prompt_def in config["prompts"]:
        register_prompt(mcp, prompt_def)

    for resource_def in config["resources"]:
        register_resource(mcp, resource_def)

    tool_count = len(config["tools"])
    prompt_count = len(config["prompts"])
    resource_count = len(config["resources"])
    logger.info(
        "MCP server configured: %d tools, %d prompts, %d resources",
        tool_count,
        prompt_count,
        resource_count,
    )

    return mcp


def main() -> None:
    """Entry point for the MCP server."""
    parser = argparse.ArgumentParser(description="MCP Server for Juju charms")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("/etc/mcp-server/config.json"),
        help="Path to the MCP definitions config file",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",  # noqa: S104
        help="Host to bind to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8081,
        help="Port to listen on",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Log level",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    mcp = create_server(args.config)
    logger.info("Starting MCP server on %s:%d", args.host, args.port)
    mcp.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
