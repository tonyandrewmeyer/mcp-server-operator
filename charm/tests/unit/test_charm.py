# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.
#
# To learn more about testing, see https://documentation.ubuntu.com/ops/latest/explanation/testing/

import json

import pytest
from ops import testing

from charm import McpServerCharm


class _NonExistentPath:
    """A stand-in for a pathlib.Path that always reports as non-existent."""

    def exists(self):
        return False


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
def test_stop(monkeypatch):
    calls = []

    def _track_stop():
        calls.append("stop")

    ctx = testing.Context(McpServerCharm)
    ctx.run(ctx.on.install(), testing.State())
    monkeypatch.setattr("charm.mcp_server.stop", _track_stop)
    ctx = testing.Context(McpServerCharm)
    ctx.run(ctx.on.stop(), testing.State())
    assert "stop" in calls


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
    restart_calls = []
    monkeypatch.setattr("charm.mcp_server.is_running", _mock_is_running)
    monkeypatch.setattr("charm.mcp_server.restart", lambda: restart_calls.append("restart"))
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
    assert "restart" in restart_calls


@pytest.mark.usefixtures("_patch_workload")
def test_oauth_relation_changed_no_restart_if_not_running(monkeypatch):
    restart_calls = []
    monkeypatch.setattr("charm.mcp_server.is_running", _mock_is_not_running)
    monkeypatch.setattr("charm.mcp_server.restart", lambda: restart_calls.append("restart"))
    ctx = testing.Context(McpServerCharm)
    oauth_relation = testing.Relation(
        endpoint="oauth",
        remote_app_data={"issuer_url": "https://idp.example.com"},
    )
    ctx.run(
        ctx.on.relation_changed(oauth_relation),
        testing.State(relations=[oauth_relation]),
    )
    assert restart_calls == []


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
def test_oauth_relation_broken_restarts_if_running(monkeypatch):
    restart_calls = []
    monkeypatch.setattr("charm.mcp_server.is_running", _mock_is_running)
    monkeypatch.setattr("charm.mcp_server.restart", lambda: restart_calls.append("restart"))
    ctx = testing.Context(McpServerCharm)
    oauth_relation = testing.Relation(
        endpoint="oauth",
        remote_app_data={"issuer_url": "https://idp.example.com"},
    )
    ctx.run(
        ctx.on.relation_broken(oauth_relation),
        testing.State(relations=[oauth_relation]),
    )
    assert "restart" in restart_calls


@pytest.mark.usefixtures("_patch_workload")
def test_get_oauth_config_no_relation(monkeypatch):
    """_get_oauth_config returns None when there is no oauth relation."""
    systemd_calls = []

    def _track_write_systemd(**kwargs):
        systemd_calls.append(kwargs)

    monkeypatch.setattr("charm.mcp_server.write_systemd_unit", _track_write_systemd)
    ctx = testing.Context(McpServerCharm)
    ctx.run(ctx.on.config_changed(), testing.State())
    assert systemd_calls[0]["oauth_config"] is None


@pytest.mark.usefixtures("_patch_workload")
def test_get_oauth_config_no_issuer_url(monkeypatch):
    """_get_oauth_config returns None when issuer_url is missing."""
    systemd_calls = []

    def _track_write_systemd(**kwargs):
        systemd_calls.append(kwargs)

    monkeypatch.setattr("charm.mcp_server.write_systemd_unit", _track_write_systemd)
    ctx = testing.Context(McpServerCharm)
    oauth_relation = testing.Relation(
        endpoint="oauth",
        remote_app_data={"client_id": "my-client"},
    )
    ctx.run(
        ctx.on.relation_changed(oauth_relation),
        testing.State(relations=[oauth_relation]),
    )
    assert systemd_calls[0]["oauth_config"] is None


@pytest.mark.usefixtures("_patch_workload")
def test_get_oauth_config_basic(monkeypatch):
    """_get_oauth_config extracts issuer_url and builds resource_server_url."""
    systemd_calls = []

    def _track_write_systemd(**kwargs):
        systemd_calls.append(kwargs)

    monkeypatch.setattr("charm.mcp_server.write_systemd_unit", _track_write_systemd)
    ctx = testing.Context(McpServerCharm)
    oauth_relation = testing.Relation(
        endpoint="oauth",
        remote_app_data={"issuer_url": "https://idp.example.com"},
    )
    ctx.run(
        ctx.on.relation_changed(oauth_relation),
        testing.State(relations=[oauth_relation]),
    )
    oauth_config = systemd_calls[0]["oauth_config"]
    assert oauth_config is not None
    assert oauth_config["issuer_url"] == "https://idp.example.com"
    assert oauth_config["resource_server_url"] == "http://localhost:8081"


@pytest.mark.usefixtures("_patch_workload")
def test_get_oauth_config_full(monkeypatch):
    """_get_oauth_config extracts all optional fields."""
    systemd_calls = []

    def _track_write_systemd(**kwargs):
        systemd_calls.append(kwargs)

    monkeypatch.setattr("charm.mcp_server.write_systemd_unit", _track_write_systemd)
    ctx = testing.Context(McpServerCharm)
    oauth_relation = testing.Relation(
        endpoint="oauth",
        remote_app_data={
            "issuer_url": "https://idp.example.com",
            "jwks_endpoint": "https://idp.example.com/.well-known/jwks.json",
            "introspection_endpoint": "https://idp.example.com/oauth2/introspect",
            "client_id": "mcp-server-client",
            "jwt_access_token": "true",
        },
    )
    ctx.run(
        ctx.on.relation_changed(oauth_relation),
        testing.State(relations=[oauth_relation]),
    )
    oauth_config = systemd_calls[0]["oauth_config"]
    assert oauth_config["issuer_url"] == "https://idp.example.com"
    assert oauth_config["jwks_endpoint"] == "https://idp.example.com/.well-known/jwks.json"
    assert oauth_config["jwks_uri"] == "https://idp.example.com/.well-known/jwks.json"
    assert oauth_config["introspection_endpoint"] == "https://idp.example.com/oauth2/introspect"
    assert oauth_config["client_id"] == "mcp-server-client"
    assert oauth_config["jwt_access_token"] is True


@pytest.mark.usefixtures("_patch_workload")
def test_get_oauth_config_with_client_secret(monkeypatch):
    """_get_oauth_config resolves client_secret from a Juju secret."""
    systemd_calls = []

    def _track_write_systemd(**kwargs):
        systemd_calls.append(kwargs)

    monkeypatch.setattr("charm.mcp_server.write_systemd_unit", _track_write_systemd)
    ctx = testing.Context(McpServerCharm)
    secret = testing.Secret(
        tracked_content={"secret": "s3cr3t-value"},
        owner=None,
    )
    oauth_relation = testing.Relation(
        endpoint="oauth",
        remote_app_data={
            "issuer_url": "https://idp.example.com",
            "client_id": "mcp-server-client",
            "client_secret_id": secret.id,
        },
    )
    ctx.run(
        ctx.on.relation_changed(oauth_relation),
        testing.State(relations=[oauth_relation], secrets=[secret]),
    )
    oauth_config = systemd_calls[0]["oauth_config"]
    assert oauth_config["client_secret"] == "s3cr3t-value"


@pytest.mark.usefixtures("_patch_workload")
def test_get_oauth_config_jwt_access_token_false(monkeypatch):
    """_get_oauth_config parses jwt_access_token=false correctly."""
    systemd_calls = []

    def _track_write_systemd(**kwargs):
        systemd_calls.append(kwargs)

    monkeypatch.setattr("charm.mcp_server.write_systemd_unit", _track_write_systemd)
    ctx = testing.Context(McpServerCharm)
    oauth_relation = testing.Relation(
        endpoint="oauth",
        remote_app_data={
            "issuer_url": "https://idp.example.com",
            "jwt_access_token": "false",
        },
    )
    ctx.run(
        ctx.on.relation_changed(oauth_relation),
        testing.State(relations=[oauth_relation]),
    )
    oauth_config = systemd_calls[0]["oauth_config"]
    assert oauth_config["jwt_access_token"] is False


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


@pytest.mark.usefixtures("_patch_workload")
def test_certificates_relation_broken_restarts_if_running(monkeypatch, tmp_path):
    restart_calls = []
    monkeypatch.setattr("charm.mcp_server.is_running", _mock_is_running)
    monkeypatch.setattr("charm.mcp_server.restart", lambda: restart_calls.append("restart"))

    # Create fake TLS files that should be removed on relation-broken.
    tls_dir = tmp_path / "tls"
    tls_dir.mkdir()
    cert = tls_dir / "cert.pem"
    key = tls_dir / "key.pem"
    ca = tls_dir / "ca.pem"
    cert.write_text("cert")
    key.write_text("key")
    ca.write_text("ca")
    monkeypatch.setattr("charm.mcp_server.TLS_CERT_PATH", cert)
    monkeypatch.setattr("charm.mcp_server.TLS_KEY_PATH", key)
    monkeypatch.setattr("charm.mcp_server.TLS_CA_PATH", ca)

    ctx = testing.Context(McpServerCharm)
    certs_relation = testing.Relation(endpoint="certificates")
    ctx.run(
        ctx.on.relation_broken(certs_relation),
        testing.State(relations=[certs_relation]),
    )
    assert "restart" in restart_calls
    assert not cert.exists()
    assert not key.exists()
    assert not ca.exists()


@pytest.mark.usefixtures("_patch_workload")
def test_certificates_relation_broken_no_restart_if_not_running(monkeypatch):
    restart_calls = []
    monkeypatch.setattr("charm.mcp_server.is_running", _mock_is_not_running)
    monkeypatch.setattr("charm.mcp_server.restart", lambda: restart_calls.append("restart"))

    ctx = testing.Context(McpServerCharm)
    certs_relation = testing.Relation(endpoint="certificates")
    ctx.run(
        ctx.on.relation_broken(certs_relation),
        testing.State(relations=[certs_relation]),
    )
    assert restart_calls == []


@pytest.mark.usefixtures("_patch_workload")
def test_config_passes_path_prefix(monkeypatch):
    """path-prefix config is passed through to write_systemd_unit."""
    systemd_calls = []

    def _track_write_systemd(**kwargs):
        systemd_calls.append(kwargs)

    monkeypatch.setattr("charm.mcp_server.write_systemd_unit", _track_write_systemd)
    monkeypatch.setattr("charm.mcp_server.TLS_CERT_PATH", _NonExistentPath())
    monkeypatch.setattr("charm.mcp_server.TLS_KEY_PATH", _NonExistentPath())
    ctx = testing.Context(McpServerCharm)
    ctx.run(
        ctx.on.config_changed(),
        testing.State(config={"path-prefix": "/myapp"}),
    )
    assert systemd_calls[0]["path_prefix"] == "/myapp"


@pytest.mark.usefixtures("_patch_workload")
def test_tls_flag_set_when_files_exist(monkeypatch, tmp_path):
    """TLS flag is True when cert and key files exist."""
    systemd_calls = []

    def _track_write_systemd(**kwargs):
        systemd_calls.append(kwargs)

    monkeypatch.setattr("charm.mcp_server.write_systemd_unit", _track_write_systemd)

    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    cert.write_text("cert")
    key.write_text("key")
    monkeypatch.setattr("charm.mcp_server.TLS_CERT_PATH", cert)
    monkeypatch.setattr("charm.mcp_server.TLS_KEY_PATH", key)

    ctx = testing.Context(McpServerCharm)
    ctx.run(ctx.on.config_changed(), testing.State())
    assert systemd_calls[0]["tls"] is True


@pytest.mark.usefixtures("_patch_workload")
def test_tls_flag_false_when_no_files(monkeypatch):
    """TLS flag is False when cert and key files do not exist."""
    systemd_calls = []

    def _track_write_systemd(**kwargs):
        systemd_calls.append(kwargs)

    monkeypatch.setattr("charm.mcp_server.write_systemd_unit", _track_write_systemd)
    monkeypatch.setattr("charm.mcp_server.TLS_CERT_PATH", _NonExistentPath())
    monkeypatch.setattr("charm.mcp_server.TLS_KEY_PATH", _NonExistentPath())

    ctx = testing.Context(McpServerCharm)
    ctx.run(ctx.on.config_changed(), testing.State())
    assert systemd_calls[0]["tls"] is False


@pytest.mark.usefixtures("_patch_workload")
def test_cos_agent_provider_metrics_endpoint():
    """COSAgentProvider is configured with the correct metrics endpoint."""
    ctx = testing.Context(McpServerCharm)
    state = testing.State(relations=[testing.Relation(endpoint="cos-agent")])
    state_out = ctx.run(ctx.on.config_changed(), state)
    assert not isinstance(state_out.unit_status, testing.ErrorStatus)


@pytest.mark.usefixtures("_patch_workload")
def test_tracing_relation_changed_restarts_if_running(monkeypatch):
    """Tracing endpoint change triggers systemd unit rewrite and restart."""
    restart_calls = []
    monkeypatch.setattr("charm.mcp_server.is_running", _mock_is_running)
    monkeypatch.setattr("charm.mcp_server.restart", lambda: restart_calls.append("restart"))
    ctx = testing.Context(McpServerCharm)
    tracing_relation = testing.Relation(endpoint="charm-tracing")
    ctx.run(
        ctx.on.relation_changed(tracing_relation),
        testing.State(relations=[tracing_relation]),
    )
    assert "restart" in restart_calls


@pytest.mark.usefixtures("_patch_workload")
def test_tracing_relation_broken_restarts_if_running(monkeypatch):
    """Tracing endpoint removal triggers systemd unit rewrite and restart."""
    restart_calls = []
    monkeypatch.setattr("charm.mcp_server.is_running", _mock_is_running)
    monkeypatch.setattr("charm.mcp_server.restart", lambda: restart_calls.append("restart"))
    ctx = testing.Context(McpServerCharm)
    tracing_relation = testing.Relation(endpoint="charm-tracing")
    ctx.run(
        ctx.on.relation_broken(tracing_relation),
        testing.State(relations=[tracing_relation]),
    )
    assert "restart" in restart_calls
