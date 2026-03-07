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
import prometheus_client
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import Prompt
from mcp.server.fastmcp.resources import FunctionResource
from mcp.types import TextContent
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from opentelemetry.sdk import trace as sdk_trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

import token_verifier as tv

logger = logging.getLogger(__name__)

# Pattern for {{placeholder}} template substitution.
TEMPLATE_PATTERN = re.compile(r"\{\{(\w+)\}\}")

# Prometheus metrics.
REQUEST_COUNT = prometheus_client.Counter(
    "mcp_requests_total",
    "Total MCP requests",
    ["method", "status"],
)
REQUEST_LATENCY = prometheus_client.Histogram(
    "mcp_request_duration_seconds",
    "MCP request latency in seconds",
    ["method"],
)
TOOL_CALLS = prometheus_client.Counter(
    "mcp_tool_calls_total",
    "Total MCP tool invocations",
    ["tool_name", "status"],
)
ACTIVE_CONNECTIONS = prometheus_client.Gauge(
    "mcp_active_connections",
    "Currently active MCP connections",
)


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


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware that records Prometheus metrics for each request."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Record request count, latency, and active connections."""
        method = request.method
        ACTIVE_CONNECTIONS.inc()
        start = time.monotonic()
        try:
            response = await call_next(request)
            REQUEST_COUNT.labels(method=method, status=response.status_code).inc()
            return response
        except Exception:
            REQUEST_COUNT.labels(method=method, status=500).inc()
            raise
        finally:
            REQUEST_LATENCY.labels(method=method).observe(time.monotonic() - start)
            ACTIVE_CONNECTIONS.dec()


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
    tool_name: str = "",
) -> Any:
    """Build a tool handler function with an explicit signature matching the input schema.

    FastMCP introspects the handler's signature to build the input schema, so
    we need named parameters rather than **kwargs.
    """

    async def tool_handler(**kwargs: Any) -> list[TextContent]:
        # Validate arguments against declared schema before execution.
        errors = validate_arguments(kwargs, input_schema)
        if errors:
            TOOL_CALLS.labels(tool_name=tool_name, status="error").inc()
            return [TextContent(type="text", text=f"Validation error: {'; '.join(errors)}")]

        handler_type = handler["type"]
        if handler_type == "exec":
            # Check command allowlist if configured.
            if command_allowlist is not None:
                executable = handler["command"][0]
                if executable not in command_allowlist:
                    TOOL_CALLS.labels(tool_name=tool_name, status="error").inc()
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
        TOOL_CALLS.labels(tool_name=tool_name, status="success").inc()
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
        handler, input_schema, properties, required, command_allowlist, tool_name=name
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
    oauth_issuer_url: str | None = None,
    oauth_resource_server_url: str | None = None,
    oauth_jwks_uri: str | None = None,
    oauth_introspection_endpoint: str | None = None,
    oauth_client_id: str | None = None,
    oauth_client_secret: str | None = None,
    oauth_jwt_access_tokens: bool = True,
    oauth_required_scopes: list[str] | None = None,
) -> FastMCP:
    """Create and configure an MCP server from a config file."""
    config = load_config(config_path)

    extra_kwargs: dict[str, Any] = {}
    if oauth_issuer_url and oauth_resource_server_url:
        verifier = tv.create_token_verifier(
            issuer_url=oauth_issuer_url,
            resource_server_url=oauth_resource_server_url,
            jwks_uri=oauth_jwks_uri,
            introspection_endpoint=oauth_introspection_endpoint,
            client_id=oauth_client_id,
            client_secret=oauth_client_secret,
            jwt_access_tokens=oauth_jwt_access_tokens,
        )
        extra_kwargs["auth"] = AuthSettings(
            issuer_url=oauth_issuer_url,  # ty: ignore[invalid-argument-type]
            resource_server_url=oauth_resource_server_url,  # ty: ignore[invalid-argument-type]
            required_scopes=oauth_required_scopes,
        )
        extra_kwargs["token_verifier"] = verifier
        logger.info("OAuth 2.1 resource server mode enabled (issuer: %s)", oauth_issuer_url)

    mcp = FastMCP("mcp-server-charm", stateless_http=True, host=host, port=port, **extra_kwargs)

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


async def _health_handler(request: Request) -> JSONResponse:
    """Lightweight health check endpoint."""
    return JSONResponse({"status": "ok"})


async def _metrics_handler(request: Request) -> Response:
    """Prometheus metrics endpoint."""
    body = prometheus_client.generate_latest()
    return Response(content=body, media_type=prometheus_client.CONTENT_TYPE_LATEST)


def _setup_tracing(otlp_endpoint: str, service_name: str = "mcp-server") -> None:
    """Initialise OpenTelemetry tracing with an OTLP HTTP exporter."""
    resource = Resource.create({"service.name": service_name})
    provider = sdk_trace.TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    logger.info("OpenTelemetry tracing enabled, exporting to %s", otlp_endpoint)


def build_app(
    mcp: FastMCP,
    *,
    path_prefix: str = "",
    auth_token: str | None = None,
    rate_limit: int | None = None,
    otlp_endpoint: str | None = None,
) -> Starlette:
    """Build the ASGI application with optional middleware and path prefix.

    When a path prefix is set, the MCP app is mounted under that prefix and a
    health endpoint is available at ``<prefix>/health``.  Without a prefix the
    MCP app is served at the root with ``/health`` alongside it.
    """
    mcp_app = mcp.streamable_http_app()

    prefix = path_prefix.strip("/")
    health_path = f"/{prefix}/health" if prefix else "/health"
    metrics_path = f"/{prefix}/metrics" if prefix else "/metrics"

    if prefix:
        # Mount the MCP Starlette app under the prefix and add utility routes
        # to a parent application.
        parent = Starlette(
            routes=[Route(health_path, _health_handler), Route(metrics_path, _metrics_handler)]
        )
        parent.mount(f"/{prefix}", mcp_app)
        app = parent
    else:
        mcp_app.routes.append(Route("/health", _health_handler))
        mcp_app.routes.append(Route("/metrics", _metrics_handler))
        app = mcp_app

    # Metrics middleware is always active to record request telemetry.
    app.add_middleware(MetricsMiddleware)  # ty: ignore[invalid-argument-type]
    if otlp_endpoint:
        _setup_tracing(otlp_endpoint)
        app.add_middleware(OpenTelemetryMiddleware)  # ty: ignore[invalid-argument-type]
    if rate_limit:
        app.add_middleware(
            RateLimitMiddleware,  # ty: ignore[invalid-argument-type]
            max_requests=rate_limit,
        )
        logger.info("Rate limiting enabled: %d requests/minute", rate_limit)
    if auth_token:
        app.add_middleware(
            BearerAuthMiddleware,  # ty: ignore[invalid-argument-type]
            token=auth_token,
        )
        logger.info("Bearer token authentication enabled")

    return app


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
        "--log-format",
        default="text",
        choices=["text", "json"],
        help="Log format: 'text' for human-readable, 'json' for structured logging",
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

    parser.add_argument(
        "--path-prefix",
        default="",
        help="URL path prefix for the MCP endpoint (e.g. /postgresql)",
    )
    parser.add_argument(
        "--tls-cert",
        default=None,
        help="Path to TLS certificate file for HTTPS",
    )
    parser.add_argument(
        "--tls-key",
        default=None,
        help="Path to TLS private key file for HTTPS",
    )
    parser.add_argument(
        "--otlp-endpoint",
        default=None,
        help="OTLP HTTP endpoint for OpenTelemetry trace export (e.g. http://localhost:4318)",
    )

    # OAuth 2.1 resource server options.
    oauth_group = parser.add_argument_group("OAuth 2.1", "Resource server authentication")
    oauth_group.add_argument("--oauth-issuer-url", default=None, help="OAuth issuer URL")
    oauth_group.add_argument(
        "--oauth-resource-server-url", default=None, help="This server's public URL"
    )
    oauth_group.add_argument("--oauth-jwks-uri", default=None, help="JWKS endpoint URL")
    oauth_group.add_argument(
        "--oauth-introspection-endpoint",
        default=None,
        help="Token introspection endpoint URL",
    )
    oauth_group.add_argument("--oauth-client-id", default=None, help="OAuth client ID")
    oauth_group.add_argument("--oauth-client-secret", default=None, help="OAuth client secret")
    oauth_group.add_argument(
        "--oauth-jwt-access-tokens",
        action="store_true",
        default=True,
        help="Expect JWT access tokens (default; use JWKS validation)",
    )
    oauth_group.add_argument(
        "--oauth-opaque-tokens",
        action="store_true",
        default=False,
        help="Expect opaque access tokens (use introspection)",
    )
    oauth_group.add_argument(
        "--oauth-required-scopes",
        nargs="*",
        default=None,
        help="Required OAuth scopes",
    )

    args = parser.parse_args()

    log_level = getattr(logging, args.log_level.upper())
    if args.log_format == "json":
        logging.basicConfig(
            level=log_level,
            format='{"timestamp":"%(asctime)s","logger":"%(name)s","level":"%(levelname)s","message":"%(message)s"}',
        )
    else:
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
        )

    jwt_access_tokens = not args.oauth_opaque_tokens

    mcp = create_server(
        args.config,
        host=args.host,
        port=args.port,
        command_allowlist=args.command_allowlist,
        oauth_issuer_url=args.oauth_issuer_url,
        oauth_resource_server_url=args.oauth_resource_server_url,
        oauth_jwks_uri=args.oauth_jwks_uri,
        oauth_introspection_endpoint=args.oauth_introspection_endpoint,
        oauth_client_id=args.oauth_client_id,
        oauth_client_secret=args.oauth_client_secret,
        oauth_jwt_access_tokens=jwt_access_tokens,
        oauth_required_scopes=args.oauth_required_scopes,
    )

    needs_uvicorn = (
        args.auth_token
        or args.rate_limit
        or args.path_prefix
        or args.tls_cert
        or args.otlp_endpoint
    )
    if needs_uvicorn:
        import uvicorn  # noqa: I001

        app = build_app(
            mcp,
            path_prefix=args.path_prefix,
            auth_token=args.auth_token,
            rate_limit=args.rate_limit,
            otlp_endpoint=args.otlp_endpoint,
        )

        ssl_kwargs: dict[str, Any] = {}
        if args.tls_cert and args.tls_key:
            ssl_kwargs["ssl_certfile"] = args.tls_cert
            ssl_kwargs["ssl_keyfile"] = args.tls_key
            logger.info("TLS enabled with cert=%s", args.tls_cert)

        logger.info("Starting MCP server on %s:%d", args.host, args.port)
        uvicorn.run(app, host=args.host, port=args.port, **ssl_kwargs)
    else:
        logger.info("Starting MCP server on %s:%d", args.host, args.port)
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
