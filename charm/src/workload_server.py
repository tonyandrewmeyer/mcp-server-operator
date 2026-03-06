# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.

"""MCP server that dynamically serves tools, prompts, and resources from a JSON config file.

The server reads declarations from a JSON config file and exposes them via
streamable HTTP. Tool/resource handlers execute shell commands or HTTP requests
as declared in the config.
"""

from __future__ import annotations

import argparse
import inspect
import json
import logging
import pathlib
import re
import subprocess
import time
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import Prompt
from mcp.server.fastmcp.resources import FunctionResource
from mcp.types import TextContent
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Pattern for {{placeholder}} template substitution.
TEMPLATE_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def validate_arguments(arguments: dict[str, Any], input_schema: dict[str, Any]) -> list[str]:
    """Validate tool arguments against the declared JSON Schema.

    Returns a list of validation error messages (empty if valid).
    Only validates type, required fields, and disallows extra properties
    — this is not a full JSON Schema validator.
    """
    errors: list[str] = []
    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))

    # Check for unexpected arguments.
    extra = set(arguments) - set(properties)
    if extra:
        errors.append(f"Unexpected arguments: {', '.join(sorted(extra))}")

    # Check required fields are present.
    missing = required - set(arguments)
    if missing:
        errors.append(f"Missing required arguments: {', '.join(sorted(missing))}")

    # Type-check provided arguments.
    type_map = {"string": str, "integer": int, "number": (int, float), "boolean": bool}
    for name, value in arguments.items():
        if name not in properties:
            continue
        expected_type = properties[name].get("type")
        if expected_type and expected_type in type_map:
            if not isinstance(value, type_map[expected_type]):
                errors.append(
                    f"Argument '{name}' expected type '{expected_type}', "
                    f"got '{type(value).__name__}'"
                )

    return errors


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces Bearer token authentication."""

    def __init__(self, app: Any, token: str):
        super().__init__(app)
        self.token = token

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Reject requests without a valid Bearer token."""
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != self.token:
            return Response("Unauthorised", status_code=401)
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple per-server rate limiter using a sliding window."""

    def __init__(self, app: Any, max_requests: int, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: list[float] = []

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Reject requests that exceed the rate limit."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        self._timestamps = [t for t in self._timestamps if t > cutoff]
        if len(self._timestamps) >= self.max_requests:
            return Response("Rate limit exceeded", status_code=429)
        self._timestamps.append(now)
        return await call_next(request)


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


def load_config(config_path: pathlib.Path) -> dict[str, Any]:
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


def _build_tool_handler(
    handler: dict[str, Any],
    input_schema: dict[str, Any],
    properties: dict[str, Any],
    required: set[str],
    command_allowlist: list[str] | None = None,
) -> Any:
    """Build a tool handler function with an explicit signature matching the input schema.

    FastMCP introspects the handler's signature to build the input schema, so
    we need named parameters rather than **kwargs.
    """

    async def tool_handler(**kwargs: Any) -> list[TextContent]:
        # Validate arguments against declared schema before execution.
        errors = validate_arguments(kwargs, input_schema)
        if errors:
            return [TextContent(type="text", text=f"Validation error: {'; '.join(errors)}")]

        handler_type = handler["type"]
        if handler_type == "exec":
            # Check command allowlist if configured.
            if command_allowlist is not None:
                executable = handler["command"][0]
                if executable not in command_allowlist:
                    return [
                        TextContent(
                            type="text",
                            text=f"Command '{executable}' is not in the allowlist",
                        )
                    ]
            output = execute_exec_handler(handler, kwargs)
        elif handler_type == "http":
            output = await execute_http_handler(handler, kwargs)
        else:
            output = f"Unknown handler type: {handler_type}"
        return [TextContent(type="text", text=output)]

    # Build a proper signature so FastMCP sees named parameters.
    params = []
    for param_name in properties:
        default = inspect.Parameter.empty if param_name in required else None
        params.append(
            inspect.Parameter(
                param_name,
                inspect.Parameter.KEYWORD_ONLY,
                default=default,
                annotation=str,
            )
        )
    tool_handler.__signature__ = inspect.Signature(params)  # ty: ignore[unresolved-attribute]

    return tool_handler


def register_tool(
    mcp: FastMCP,
    tool_def: dict[str, Any],
    command_allowlist: list[str] | None = None,
) -> None:
    """Register a single tool definition with the MCP server."""
    name = tool_def["name"]
    description = tool_def["description"]
    input_schema = tool_def.get("input_schema", {})
    handler = tool_def["handler"]

    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))

    tool_handler = _build_tool_handler(
        handler, input_schema, properties, required, command_allowlist
    )

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

    prompt = Prompt.from_function(prompt_handler, name=name, description=description)
    mcp.add_prompt(prompt)
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

    resource = FunctionResource(
        uri=uri,
        name=name,
        description=description,
        mime_type=mime_type,
        fn=resource_handler,
    )
    mcp.add_resource(resource)
    logger.info("Registered resource: %s (%s)", name, uri)


def create_server(
    config_path: pathlib.Path,
    host: str = "0.0.0.0",  # noqa: S104
    port: int = 8081,
    command_allowlist: list[str] | None = None,
) -> FastMCP:
    """Create and configure an MCP server from a config file."""
    config = load_config(config_path)

    mcp = FastMCP("mcp-server-charm", stateless_http=True, host=host, port=port)

    for tool_def in config["tools"]:
        register_tool(mcp, tool_def, command_allowlist=command_allowlist)

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
        type=pathlib.Path,
        default=pathlib.Path("/etc/mcp-server/config.json"),
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
    parser.add_argument(
        "--auth-token",
        default=None,
        help="Bearer token for authentication (disabled if not set)",
    )
    parser.add_argument(
        "--rate-limit",
        type=int,
        default=None,
        help="Maximum requests per minute (disabled if not set)",
    )
    parser.add_argument(
        "--command-allowlist",
        nargs="*",
        default=None,
        help="Allowed executable names for exec handlers (all allowed if not set)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    mcp = create_server(
        args.config,
        host=args.host,
        port=args.port,
        command_allowlist=args.command_allowlist,
    )

    needs_middleware = args.auth_token or args.rate_limit
    if needs_middleware:
        import uvicorn  # noqa: I001

        app = mcp.streamable_http_app()
        if args.rate_limit:
            app.add_middleware(
                RateLimitMiddleware,  # ty: ignore[invalid-argument-type]
                max_requests=args.rate_limit,
            )
            logger.info("Rate limiting enabled: %d requests/minute", args.rate_limit)
        if args.auth_token:
            app.add_middleware(
                BearerAuthMiddleware,  # ty: ignore[invalid-argument-type]
                token=args.auth_token,
            )
            logger.info("Bearer token authentication enabled")

        logger.info("Starting MCP server on %s:%d", args.host, args.port)
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        logger.info("Starting MCP server on %s:%d", args.host, args.port)
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
