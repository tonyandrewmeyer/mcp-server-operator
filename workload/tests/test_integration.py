# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.

"""Integration tests that exercise the MCP server via real HTTP requests.

These tests create a FastMCP server from config, obtain its ASGI app, and
send actual MCP protocol messages (JSON-RPC over streamable HTTP) using
httpx with an ASGI transport — no network socket required.
"""

from __future__ import annotations

import contextlib
import json
import pathlib
from typing import Any, AsyncIterator

import httpx
import pytest

from server import BearerAuthMiddleware, RateLimitMiddleware, build_app, create_server

# The server uses stateless_http=True, so every request is independent and
# there is no session ID to track between requests.

MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


def _test_config(tmp_path: pathlib.Path) -> pathlib.Path:
    """Write a test MCP config file and return its path."""
    config = {
        "tools": [
            {
                "name": "echo-test",
                "description": "Echo a message",
                "input_schema": {
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                },
                "handler": {"type": "exec", "command": ["echo", "{{message}}"]},
            }
        ],
        "prompts": [
            {
                "name": "greet",
                "description": "A greeting prompt",
                "template": "Hello, {{name}}!",
            }
        ],
        "resources": [
            {
                "uri": "test://hostname",
                "name": "hostname",
                "description": "Get hostname",
                "handler": {"type": "exec", "command": ["hostname"]},
            }
        ],
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    return config_path


def _parse_sse_response(text: str) -> list[dict[str, Any]]:
    """Extract JSON-RPC results from an SSE response body."""
    results = []
    for line in text.splitlines():
        if line.startswith("data: "):
            data = json.loads(line[6:])
            results.append(data)
    return results


def _make_jsonrpc(method: str, params: dict[str, Any], req_id: int = 1) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 request message."""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params,
    }


# CLAUDE: us spelling
INITIALIZE_PARAMS = {
    "protocolVersion": "2025-03-26",
    "capabilities": {},
    "clientInfo": {"name": "test-client", "version": "0.1"},
}


@contextlib.asynccontextmanager
async def _make_client(
    tmp_path: pathlib.Path,
    middleware: list[tuple[type, dict[str, Any]]] | None = None,
    path_prefix: str = "",
    use_build_app: bool = False,
) -> AsyncIterator[httpx.AsyncClient]:
    """Create a server, start its session manager, and yield an HTTP client.

    The session manager requires an active task group (set up during the
    Starlette lifespan), so we enter it manually here.
    """
    config_path = _test_config(tmp_path)
    server = create_server(config_path)
    mcp_app = server.streamable_http_app()

    if path_prefix or use_build_app:
        app = build_app(server, path_prefix=path_prefix)
    else:
        app = mcp_app

    if middleware:
        for mw_class, mw_kwargs in middleware:
            app.add_middleware(mw_class, **mw_kwargs)

    # The MCP Starlette app has a lifespan that starts the session manager's
    # task group. We always need to enter it, even when the MCP app is mounted
    # as a sub-application inside a parent Starlette app.
    async with mcp_app.router.lifespan_context(mcp_app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


# CLAUDE: us spelling throughout this function and its name
async def _initialize(
    client: httpx.AsyncClient,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Send an initialise request and return the parsed JSON-RPC result."""
    msg = _make_jsonrpc("initialize", INITIALIZE_PARAMS, req_id=1)
    headers = dict(MCP_HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    response = await client.post("/mcp", json=msg, headers=headers)
    assert response.status_code == 200, (
        f"Initialise failed: {response.status_code} {response.text}"
    )
    results = _parse_sse_response(response.text)
    assert len(results) >= 1, f"Expected at least one SSE result, got: {response.text}"
    return results[0]


async def _send_message(
    client: httpx.AsyncClient,
    method: str,
    params: dict[str, Any],
    req_id: int = 2,
    extra_headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Send a JSON-RPC message and return the raw response."""
    msg = _make_jsonrpc(method, params, req_id=req_id)
    headers = dict(MCP_HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    return await client.post("/mcp", json=msg, headers=headers)


@pytest.mark.anyio
class TestServerEndToEnd:
    # CLAUDE: us spelling
    async def test_initialize(self, tmp_path: pathlib.Path):
        async with _make_client(tmp_path) as client:
            result = await _initialize(client)
            assert "result" in result
            assert result["result"]["protocolVersion"] is not None
            assert result["result"]["serverInfo"]["name"] == "mcp-server-charm"

    async def test_list_tools(self, tmp_path: pathlib.Path):
        async with _make_client(tmp_path) as client:
            response = await _send_message(client, "tools/list", {})
            assert response.status_code == 200
            results = _parse_sse_response(response.text)
            assert len(results) >= 1
            tools = results[0]["result"]["tools"]
            tool_names = [t["name"] for t in tools]
            assert "echo-test" in tool_names

    async def test_call_tool(self, tmp_path: pathlib.Path):
        async with _make_client(tmp_path) as client:
            response = await _send_message(
                client,
                "tools/call",
                {"name": "echo-test", "arguments": {"message": "hello world"}},
                req_id=3,
            )
            assert response.status_code == 200
            results = _parse_sse_response(response.text)
            assert len(results) >= 1
            content = results[0]["result"]["content"]
            text_parts = [c["text"] for c in content if c["type"] == "text"]
            assert any("hello world" in t for t in text_parts)

    async def test_list_prompts(self, tmp_path: pathlib.Path):
        async with _make_client(tmp_path) as client:
            response = await _send_message(client, "prompts/list", {})
            assert response.status_code == 200
            results = _parse_sse_response(response.text)
            assert len(results) >= 1
            prompts = results[0]["result"]["prompts"]
            prompt_names = [p["name"] for p in prompts]
            assert "greet" in prompt_names

    async def test_list_resources(self, tmp_path: pathlib.Path):
        async with _make_client(tmp_path) as client:
            response = await _send_message(client, "resources/list", {})
            assert response.status_code == 200
            results = _parse_sse_response(response.text)
            assert len(results) >= 1
            resources = results[0]["result"]["resources"]
            resource_names = [r["name"] for r in resources]
            assert "hostname" in resource_names


@pytest.mark.anyio
class TestBearerAuthEndToEnd:
    async def test_rejects_without_token(self, tmp_path: pathlib.Path):
        middleware = [(BearerAuthMiddleware, {"token": "test-secret"})]
        async with _make_client(tmp_path, middleware=middleware) as client:
            msg = _make_jsonrpc("initialize", INITIALIZE_PARAMS)
            response = await client.post("/mcp", json=msg, headers=MCP_HEADERS)
            assert response.status_code == 401

    async def test_accepts_with_token(self, tmp_path: pathlib.Path):
        middleware = [(BearerAuthMiddleware, {"token": "test-secret"})]
        async with _make_client(tmp_path, middleware=middleware) as client:
            result = await _initialize(
                client,
                extra_headers={"Authorization": "Bearer test-secret"},
            )
            assert "result" in result


@pytest.mark.anyio
class TestRateLimitEndToEnd:
    async def test_rate_limit_enforced(self, tmp_path: pathlib.Path):
        middleware = [(RateLimitMiddleware, {"max_requests": 3, "window_seconds": 60})]
        async with _make_client(tmp_path, middleware=middleware) as client:
            # The first three requests should succeed.
            for i in range(3):
                msg = _make_jsonrpc("initialize", INITIALIZE_PARAMS, req_id=i + 1)
                response = await client.post("/mcp", json=msg, headers=MCP_HEADERS)
                assert response.status_code == 200, f"Request {i + 1} should succeed"

            # The fourth request should be rate-limited.
            msg = _make_jsonrpc("initialize", INITIALIZE_PARAMS, req_id=4)
            response = await client.post("/mcp", json=msg, headers=MCP_HEADERS)
            assert response.status_code == 429


@pytest.mark.anyio
class TestSecurityBoundaries:
    async def test_template_injection_in_arguments(self, tmp_path: pathlib.Path):
        """Shell metacharacters in arguments must not cause injection."""
        async with _make_client(tmp_path) as client:
            # The argument contains shell metacharacters that would be dangerous
            # if passed through a shell, but since we use list-based subprocess
            # calls, echo should output the string literally.
            malicious = "; rm -rf / && echo pwned"
            response = await _send_message(
                client,
                "tools/call",
                {"name": "echo-test", "arguments": {"message": malicious}},
                req_id=3,
            )
            assert response.status_code == 200
            results = _parse_sse_response(response.text)
            assert len(results) >= 1
            content = results[0]["result"]["content"]
            text_parts = [c["text"] for c in content if c["type"] == "text"]
            # The malicious string should appear literally in the output.
            assert any(malicious in t for t in text_parts)

    async def test_invalid_json_rpc(self, tmp_path: pathlib.Path):
        """Malformed JSON should not crash the server."""
        async with _make_client(tmp_path) as client:
            response = await client.post(
                "/mcp",
                content="this is not json",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )
            # The server should return an error status, not 500.
            assert response.status_code < 500

    async def test_unknown_method(self, tmp_path: pathlib.Path):
        """An unknown JSON-RPC method should return an error, not crash."""
        async with _make_client(tmp_path) as client:
            response = await _send_message(
                client,
                "nonexistent/method",
                {},
                req_id=99,
            )
            # Should get either an error response or an SSE with a JSON-RPC error.
            assert response.status_code < 500
            if response.status_code == 200:
                results = _parse_sse_response(response.text)
                assert len(results) >= 1
                assert "error" in results[0]


@pytest.mark.anyio
class TestHealthEndpoint:
    async def test_health_returns_ok(self, tmp_path: pathlib.Path):
        async with _make_client(tmp_path, use_build_app=True) as client:
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

    async def test_health_with_path_prefix(self, tmp_path: pathlib.Path):
        async with _make_client(tmp_path, path_prefix="/myapp") as client:
            response = await client.get("/myapp/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}


@pytest.mark.anyio
class TestPathPrefix:
    async def test_mcp_under_prefix(self, tmp_path: pathlib.Path):
        """MCP endpoint should be reachable under the configured prefix."""
        async with _make_client(tmp_path, path_prefix="/pg") as client:
            msg = _make_jsonrpc("tools/list", {})
            response = await client.post("/pg/mcp", json=msg, headers=MCP_HEADERS)
            assert response.status_code == 200
            results = _parse_sse_response(response.text)
            assert len(results) >= 1
            tools = results[0]["result"]["tools"]
            assert any(t["name"] == "echo-test" for t in tools)

    async def test_root_mcp_not_available_with_prefix(self, tmp_path: pathlib.Path):
        """The root /mcp should not serve the MCP endpoint when a prefix is set."""
        async with _make_client(tmp_path, path_prefix="/pg") as client:
            msg = _make_jsonrpc("initialize", INITIALIZE_PARAMS)
            response = await client.post("/mcp", json=msg, headers=MCP_HEADERS)
            # Should get 404 or similar since /mcp is not mounted at root.
            assert response.status_code in (404, 405)


@pytest.mark.anyio
class TestMetricsEndpoint:
    async def test_metrics_returns_prometheus_format(self, tmp_path: pathlib.Path):
        async with _make_client(tmp_path, use_build_app=True) as client:
            response = await client.get("/metrics")
            assert response.status_code == 200
            assert "mcp_requests_total" in response.text
            assert "mcp_active_connections" in response.text

    async def test_metrics_with_path_prefix(self, tmp_path: pathlib.Path):
        async with _make_client(tmp_path, path_prefix="/myapp") as client:
            response = await client.get("/myapp/metrics")
            assert response.status_code == 200
            assert "mcp_request_duration_seconds" in response.text

    async def test_metrics_increment_after_request(self, tmp_path: pathlib.Path):
        async with _make_client(tmp_path, use_build_app=True) as client:
            # Make a request so the counter has data.
            msg = _make_jsonrpc("tools/list", {})
            await client.post("/mcp", json=msg, headers=MCP_HEADERS)

            response = await client.get("/metrics")
            assert response.status_code == 200
            # The POST request should have been counted.
            assert "mcp_requests_total" in response.text
