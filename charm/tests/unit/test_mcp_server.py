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

    @pytest.mark.usefixtures("_patch_subprocess")
    def test_write_systemd_unit_with_path_prefix(self, monkeypatch, tmp_path):
        unit_path = tmp_path / "mcp-server.service"
        monkeypatch.setattr(mcp_server, "SYSTEMD_UNIT_PATH", unit_path)

        mcp_server.write_systemd_unit(path_prefix="/myapp")

        content = unit_path.read_text()
        assert "--path-prefix /myapp" in content

    @pytest.mark.usefixtures("_patch_subprocess")
    def test_write_systemd_unit_with_tls(self, monkeypatch, tmp_path):
        unit_path = tmp_path / "mcp-server.service"
        monkeypatch.setattr(mcp_server, "SYSTEMD_UNIT_PATH", unit_path)

        mcp_server.write_systemd_unit(tls=True)

        content = unit_path.read_text()
        assert "--tls-cert" in content
        assert "--tls-key" in content

    @pytest.mark.usefixtures("_patch_subprocess")
    def test_write_systemd_unit_with_otlp_endpoint(self, monkeypatch, tmp_path):
        unit_path = tmp_path / "mcp-server.service"
        monkeypatch.setattr(mcp_server, "SYSTEMD_UNIT_PATH", unit_path)

        mcp_server.write_systemd_unit(otlp_endpoint="http://tempo:4318")

        content = unit_path.read_text()
        assert "--otlp-endpoint http://tempo:4318" in content

    @pytest.mark.usefixtures("_patch_subprocess")
    def test_write_systemd_unit_no_otlp_when_empty(self, monkeypatch, tmp_path):
        unit_path = tmp_path / "mcp-server.service"
        monkeypatch.setattr(mcp_server, "SYSTEMD_UNIT_PATH", unit_path)

        mcp_server.write_systemd_unit()

        content = unit_path.read_text()
        assert "--otlp-endpoint" not in content


class TestWriteTlsFiles:
    def test_write_tls_files(self, monkeypatch, tmp_path):
        tls_dir = tmp_path / "tls"
        cert_path = tls_dir / "cert.pem"
        key_path = tls_dir / "key.pem"
        ca_path = tls_dir / "ca.pem"
        monkeypatch.setattr(mcp_server, "TLS_DIR", tls_dir)
        monkeypatch.setattr(mcp_server, "TLS_CERT_PATH", cert_path)
        monkeypatch.setattr(mcp_server, "TLS_KEY_PATH", key_path)
        monkeypatch.setattr(mcp_server, "TLS_CA_PATH", ca_path)

        mcp_server.write_tls_files(
            cert="-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----",
            key="-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----",
            ca_chain="-----BEGIN CERTIFICATE-----\nca\n-----END CERTIFICATE-----",
        )

        assert cert_path.read_text().startswith("-----BEGIN CERTIFICATE-----")
        assert key_path.read_text().startswith("-----BEGIN PRIVATE KEY-----")
        assert ca_path.read_text().startswith("-----BEGIN CERTIFICATE-----")
        # Key file should have restricted permissions.
        assert key_path.stat().st_mode & 0o777 == 0o600

    def test_write_tls_files_no_ca(self, monkeypatch, tmp_path):
        tls_dir = tmp_path / "tls"
        cert_path = tls_dir / "cert.pem"
        key_path = tls_dir / "key.pem"
        ca_path = tls_dir / "ca.pem"
        monkeypatch.setattr(mcp_server, "TLS_DIR", tls_dir)
        monkeypatch.setattr(mcp_server, "TLS_CERT_PATH", cert_path)
        monkeypatch.setattr(mcp_server, "TLS_KEY_PATH", key_path)
        monkeypatch.setattr(mcp_server, "TLS_CA_PATH", ca_path)

        mcp_server.write_tls_files(cert="cert-data", key="key-data")

        assert cert_path.exists()
        assert key_path.exists()
        assert not ca_path.exists()


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
