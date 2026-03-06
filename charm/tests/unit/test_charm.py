# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.
#
# To learn more about testing, see https://documentation.ubuntu.com/ops/latest/explanation/testing/

import json

import pytest
from ops import testing

from charm import McpServerCharm

MCP_DEFINITIONS = {
    "tools": [
        {
            "name": "hello",
            "description": "Say hello",
            "input_schema": {"type": "object", "properties": {}, "required": []},
            "handler": {"type": "exec", "command": ["echo", "hello"]},
        }
    ],
    "prompts": [],
    "resources": [],
}


def _noop(*args, **kwargs):
    pass


def _mock_get_version():
    return "1.0.0"


def _mock_is_running():
    return True


def _mock_is_not_running():
    return False


@pytest.fixture()
def _patch_workload(monkeypatch):
    """Patch out all mcp_server workload calls."""
    monkeypatch.setattr("charm.mcp_server.install", _noop)
    monkeypatch.setattr("charm.mcp_server.write_config", _noop)
    monkeypatch.setattr("charm.mcp_server.write_systemd_unit", _noop)
    monkeypatch.setattr("charm.mcp_server.start", _noop)
    monkeypatch.setattr("charm.mcp_server.restart", _noop)
    monkeypatch.setattr("charm.mcp_server.stop", _noop)
    monkeypatch.setattr("charm.mcp_server.get_version", _mock_get_version)
    monkeypatch.setattr("charm.mcp_server.is_running", _mock_is_not_running)


@pytest.mark.usefixtures("_patch_workload")
def test_install():
    ctx = testing.Context(McpServerCharm)
    state_out = ctx.run(ctx.on.install(), testing.State())
    assert state_out.unit_status == testing.MaintenanceStatus("installing MCP server")


@pytest.mark.usefixtures("_patch_workload")
def test_start_without_relation():
    ctx = testing.Context(McpServerCharm)
    state_out = ctx.run(ctx.on.start(), testing.State())
    assert state_out.unit_status == testing.WaitingStatus("waiting for mcp relation data")


@pytest.mark.usefixtures("_patch_workload")
def test_start_with_relation(monkeypatch):
    monkeypatch.setattr("charm.mcp_server.get_version", _mock_get_version)
    ctx = testing.Context(McpServerCharm)
    relation = testing.SubordinateRelation(
        endpoint="mcp",
        remote_app_data={"mcp_definitions": json.dumps(MCP_DEFINITIONS)},
    )
    state_out = ctx.run(ctx.on.start(), testing.State(relations=[relation]))
    assert state_out.unit_status == testing.ActiveStatus()
    assert state_out.workload_version == "1.0.0"


@pytest.mark.usefixtures("_patch_workload")
def test_mcp_relation_changed(monkeypatch):
    monkeypatch.setattr("charm.mcp_server.get_version", _mock_get_version)
    ctx = testing.Context(McpServerCharm)
    relation = testing.SubordinateRelation(
        endpoint="mcp",
        remote_app_data={"mcp_definitions": json.dumps(MCP_DEFINITIONS)},
    )
    state_out = ctx.run(ctx.on.relation_changed(relation), testing.State(relations=[relation]))
    assert state_out.unit_status == testing.ActiveStatus()


@pytest.mark.usefixtures("_patch_workload")
def test_mcp_relation_broken():
    ctx = testing.Context(McpServerCharm)
    relation = testing.SubordinateRelation(
        endpoint="mcp",
        remote_app_data={"mcp_definitions": json.dumps(MCP_DEFINITIONS)},
    )
    state_out = ctx.run(ctx.on.relation_broken(relation), testing.State(relations=[relation]))
    assert state_out.unit_status == testing.BlockedStatus("no mcp relation")


@pytest.mark.usefixtures("_patch_workload")
def test_stop():
    calls = []

    def _track_stop():
        calls.append("stop")

    ctx = testing.Context(McpServerCharm)
    # Temporarily replace the patched stop with one that records the call.
    ctx.run(ctx.on.install(), testing.State())
    import charm

    original = charm.mcp_server.stop
    charm.mcp_server.stop = _track_stop
    try:
        ctx = testing.Context(McpServerCharm)
        ctx.run(ctx.on.stop(), testing.State())
        assert "stop" in calls
    finally:
        charm.mcp_server.stop = original


@pytest.mark.usefixtures("_patch_workload")
def test_config_changed_restarts_if_running(monkeypatch):
    monkeypatch.setattr("charm.mcp_server.is_running", _mock_is_running)
    ctx = testing.Context(McpServerCharm)
    state_out = ctx.run(ctx.on.config_changed(), testing.State())
    assert isinstance(state_out.unit_status, testing.ActiveStatus) or not isinstance(
        state_out.unit_status, testing.ErrorStatus
    )


@pytest.mark.usefixtures("_patch_workload")
def test_config_changed_no_restart_if_not_running(monkeypatch):
    restart_calls = []

    def _track_restart():
        restart_calls.append("restart")

    monkeypatch.setattr("charm.mcp_server.is_running", _mock_is_not_running)
    monkeypatch.setattr("charm.mcp_server.restart", _track_restart)
    ctx = testing.Context(McpServerCharm)
    ctx.run(ctx.on.config_changed(), testing.State())
    assert restart_calls == []


@pytest.mark.usefixtures("_patch_workload")
def test_oauth_relation_changed_restarts_if_running(monkeypatch):
    monkeypatch.setattr("charm.mcp_server.is_running", _mock_is_running)
    ctx = testing.Context(McpServerCharm)
    oauth_relation = testing.Relation(
        endpoint="oauth",
        remote_app_data={"issuer_url": "https://idp.example.com"},
    )
    state_out = ctx.run(
        ctx.on.relation_changed(oauth_relation),
        testing.State(relations=[oauth_relation]),
    )
    assert not isinstance(state_out.unit_status, testing.ErrorStatus)


@pytest.mark.usefixtures("_patch_workload")
def test_oauth_relation_broken(monkeypatch):
    monkeypatch.setattr("charm.mcp_server.is_running", _mock_is_not_running)
    ctx = testing.Context(McpServerCharm)
    oauth_relation = testing.Relation(
        endpoint="oauth",
        remote_app_data={"issuer_url": "https://idp.example.com"},
    )
    state_out = ctx.run(
        ctx.on.relation_broken(oauth_relation),
        testing.State(relations=[oauth_relation]),
    )
    assert not isinstance(state_out.unit_status, testing.ErrorStatus)


@pytest.mark.usefixtures("_patch_workload")
def test_mcp_relation_changed_starts_if_not_running(monkeypatch):
    start_calls = []
    restart_calls = []

    def _track_start():
        start_calls.append("start")

    def _track_restart():
        restart_calls.append("restart")

    monkeypatch.setattr("charm.mcp_server.is_running", _mock_is_not_running)
    monkeypatch.setattr("charm.mcp_server.start", _track_start)
    monkeypatch.setattr("charm.mcp_server.restart", _track_restart)
    monkeypatch.setattr("charm.mcp_server.get_version", _mock_get_version)
    ctx = testing.Context(McpServerCharm)
    relation = testing.SubordinateRelation(
        endpoint="mcp",
        remote_app_data={"mcp_definitions": json.dumps(MCP_DEFINITIONS)},
    )
    state_out = ctx.run(ctx.on.relation_changed(relation), testing.State(relations=[relation]))
    assert state_out.unit_status == testing.ActiveStatus()
    assert "start" in start_calls
    assert restart_calls == []
