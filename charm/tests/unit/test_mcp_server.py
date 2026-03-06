# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.

import json
import subprocess

import pytest

import mcp_server


def _noop_run(*args, **kwargs):
    """Stub for subprocess.run that does nothing."""
    return subprocess.CompletedProcess(args=args[0], returncode=0)


@pytest.fixture()
def _patch_subprocess(monkeypatch):
    """Prevent real subprocess calls."""
    monkeypatch.setattr(subprocess, "run", _noop_run)


class TestOAuthExtraArgs:
    def test_oauth_extra_args_full(self):
        oauth_config = {
            "issuer_url": "https://idp.example.com",
            "resource_server_url": "http://localhost:8081",
            "jwks_uri": "https://idp.example.com/.well-known/jwks.json",
            "introspection_endpoint": "https://idp.example.com/introspect",
            "client_id": "my-client",
            "client_secret": "s3cret",
            "jwt_access_token": True,
        }
        result = mcp_server._oauth_extra_args(oauth_config)
        assert "--oauth-issuer-url https://idp.example.com" in result
        assert "--oauth-resource-server-url http://localhost:8081" in result
        assert "--oauth-jwks-uri https://idp.example.com/.well-known/jwks.json" in result
        assert "--oauth-introspection-endpoint https://idp.example.com/introspect" in result
        assert "--oauth-client-id my-client" in result
        assert "--oauth-client-secret s3cret" in result
        # jwt_access_token is True, so opaque tokens flag should not appear.
        assert "--oauth-opaque-tokens" not in result

    def test_oauth_extra_args_minimal(self):
        oauth_config = {
            "issuer_url": "https://idp.example.com",
            "resource_server_url": "http://localhost:8081",
        }
        result = mcp_server._oauth_extra_args(oauth_config)
        assert "--oauth-issuer-url https://idp.example.com" in result
        assert "--oauth-resource-server-url http://localhost:8081" in result
        assert "--oauth-jwks-uri" not in result
        assert "--oauth-introspection-endpoint" not in result
        assert "--oauth-client-id" not in result
        assert "--oauth-client-secret" not in result

    def test_oauth_extra_args_opaque_tokens(self):
        oauth_config = {
            "issuer_url": "https://idp.example.com",
            "resource_server_url": "http://localhost:8081",
            "jwt_access_token": False,
        }
        result = mcp_server._oauth_extra_args(oauth_config)
        assert "--oauth-opaque-tokens" in result


class TestWriteSystemdUnit:
    @pytest.mark.usefixtures("_patch_subprocess")
    def test_write_systemd_unit_basic(self, monkeypatch, tmp_path):
        unit_path = tmp_path / "mcp-server.service"
        monkeypatch.setattr(mcp_server, "SYSTEMD_UNIT_PATH", unit_path)

        mcp_server.write_systemd_unit(port=9090, log_level="debug")

        content = unit_path.read_text()
        assert "--port 9090" in content
        assert "--log-level debug" in content
        assert "ExecStart=" in content
        assert "--auth-token" not in content

    @pytest.mark.usefixtures("_patch_subprocess")
    def test_write_systemd_unit_with_oauth(self, monkeypatch, tmp_path):
        unit_path = tmp_path / "mcp-server.service"
        monkeypatch.setattr(mcp_server, "SYSTEMD_UNIT_PATH", unit_path)

        oauth_config = {
            "issuer_url": "https://idp.example.com",
            "resource_server_url": "http://localhost:8081",
        }
        mcp_server.write_systemd_unit(oauth_config=oauth_config)

        content = unit_path.read_text()
        assert "--oauth-issuer-url https://idp.example.com" in content
        assert "--oauth-resource-server-url http://localhost:8081" in content


class TestWriteConfig:
    def test_write_config(self, monkeypatch, tmp_path):
        config_dir = tmp_path / "mcp-server"
        config_path = config_dir / "config.json"
        monkeypatch.setattr(mcp_server, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(mcp_server, "CONFIG_PATH", config_path)

        definitions = {
            "tools": [{"name": "greet", "description": "Say hello"}],
            "prompts": [],
            "resources": [],
        }
        mcp_server.write_config(definitions)

        assert config_path.exists()
        written = json.loads(config_path.read_text())
        assert written == definitions
