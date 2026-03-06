# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.


import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from token_verifier import (
    IntrospectionTokenVerifier,
    JWTTokenVerifier,
    _parse_scopes,
    create_token_verifier,
)


def _generate_rsa_key():
    """Generate a test RSA private key."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class TestParseScopes:
    def test_string_scopes(self):
        assert _parse_scopes({"scope": "read write"}) == ["read", "write"]

    def test_list_scopes(self):
        assert _parse_scopes({"scope": ["read", "write"]}) == ["read", "write"]

    def test_missing_scopes(self):
        assert _parse_scopes({}) == []

    def test_empty_string(self):
        assert _parse_scopes({"scope": ""}) == []


class TestCreateTokenVerifier:
    def test_creates_jwt_verifier(self):
        verifier = create_token_verifier(
            issuer_url="https://idp.example.com",
            resource_server_url="https://mcp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            jwt_access_tokens=True,
        )
        assert isinstance(verifier, JWTTokenVerifier)

    def test_creates_introspection_verifier(self):
        verifier = create_token_verifier(
            issuer_url="https://idp.example.com",
            resource_server_url="https://mcp.example.com",
            introspection_endpoint="https://idp.example.com/introspect",
            client_id="my-client",
            client_secret="my-secret",
            jwt_access_tokens=False,
        )
        assert isinstance(verifier, IntrospectionTokenVerifier)

    def test_raises_on_incomplete_config(self):
        with pytest.raises(ValueError, match="OAuth configuration incomplete"):
            create_token_verifier(
                issuer_url="https://idp.example.com",
                resource_server_url="https://mcp.example.com",
                jwt_access_tokens=False,
            )


class TestJWTTokenVerifier:
    @pytest.mark.anyio()
    async def test_rejects_invalid_token(self):
        verifier = JWTTokenVerifier(
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            issuer="https://idp.example.com",
            audience="https://mcp.example.com",
        )
        result = await verifier.verify_token("not.a.valid.jwt")
        assert result is None


class TestIntrospectionTokenVerifier:
    @pytest.mark.anyio()
    async def test_rejects_on_connection_error(self):
        verifier = IntrospectionTokenVerifier(
            introspection_endpoint="http://localhost:1/introspect",
            client_id="client",
            client_secret="secret",
        )
        result = await verifier.verify_token("some-opaque-token")
        assert result is None
