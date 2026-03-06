# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.


import json
import time
import unittest.mock

import httpx
import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization
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


def _rsa_public_jwk(private_key, kid="test-key-1"):
    """Build a JWK dict from an RSA private key's public component."""
    from jwt.algorithms import RSAAlgorithm

    pub_json = RSAAlgorithm.to_jwk(private_key.public_key())
    jwk = json.loads(pub_json)
    jwk["kid"] = kid
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    return jwk


def _sign_jwt(private_key, claims, kid="test-key-1"):
    """Sign a JWT with the given RSA private key."""
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return pyjwt.encode(claims, pem, algorithm="RS256", headers={"kid": kid})


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

    @pytest.mark.anyio()
    async def test_accepts_valid_jwt(self):
        """Sign a JWT with a test RSA key and verify via mocked JWKS."""
        private_key = _generate_rsa_key()
        jwk = _rsa_public_jwk(private_key)

        verifier = JWTTokenVerifier(
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            issuer="https://idp.example.com",
            audience="https://mcp.example.com",
        )

        claims = {
            "iss": "https://idp.example.com",
            "sub": "user-123",
            "aud": "https://mcp.example.com",
            "exp": int(time.time()) + 3600,
            "client_id": "test-client",
            "scope": "read write",
        }
        token = _sign_jwt(private_key, claims)

        # Mock the JWKS client to return our test key without network access.
        with unittest.mock.patch.object(
            verifier._jwks_client,
            "get_signing_key_from_jwt",
            return_value=pyjwt.PyJWK(jwk),
        ):
            result = await verifier.verify_token(token)

        assert result is not None
        assert result.client_id == "test-client"
        assert result.scopes == ["read", "write"]
        assert result.expires_at == claims["exp"]

    @pytest.mark.anyio()
    async def test_rejects_expired_jwt(self):
        """An expired JWT should be rejected."""
        private_key = _generate_rsa_key()
        jwk = _rsa_public_jwk(private_key)

        verifier = JWTTokenVerifier(
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            issuer="https://idp.example.com",
            audience="https://mcp.example.com",
        )

        claims = {
            "iss": "https://idp.example.com",
            "sub": "user-123",
            "aud": "https://mcp.example.com",
            "exp": int(time.time()) - 3600,
            "client_id": "test-client",
        }
        token = _sign_jwt(private_key, claims)

        with unittest.mock.patch.object(
            verifier._jwks_client,
            "get_signing_key_from_jwt",
            return_value=pyjwt.PyJWK(jwk),
        ):
            result = await verifier.verify_token(token)

        assert result is None

    @pytest.mark.anyio()
    async def test_rejects_wrong_issuer(self):
        """A JWT from a different issuer should be rejected."""
        private_key = _generate_rsa_key()
        jwk = _rsa_public_jwk(private_key)

        verifier = JWTTokenVerifier(
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            issuer="https://idp.example.com",
            audience="https://mcp.example.com",
        )

        claims = {
            "iss": "https://evil.example.com",
            "sub": "user-123",
            "aud": "https://mcp.example.com",
            "exp": int(time.time()) + 3600,
        }
        token = _sign_jwt(private_key, claims)

        with unittest.mock.patch.object(
            verifier._jwks_client,
            "get_signing_key_from_jwt",
            return_value=pyjwt.PyJWK(jwk),
        ):
            result = await verifier.verify_token(token)

        assert result is None

    @pytest.mark.anyio()
    async def test_rejects_wrong_audience(self):
        """A JWT for a different audience should be rejected."""
        private_key = _generate_rsa_key()
        jwk = _rsa_public_jwk(private_key)

        verifier = JWTTokenVerifier(
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            issuer="https://idp.example.com",
            audience="https://mcp.example.com",
        )

        claims = {
            "iss": "https://idp.example.com",
            "sub": "user-123",
            "aud": "https://other-service.example.com",
            "exp": int(time.time()) + 3600,
        }
        token = _sign_jwt(private_key, claims)

        with unittest.mock.patch.object(
            verifier._jwks_client,
            "get_signing_key_from_jwt",
            return_value=pyjwt.PyJWK(jwk),
        ):
            result = await verifier.verify_token(token)

        assert result is None

    @pytest.mark.anyio()
    async def test_rejects_wrong_signing_key(self):
        """A JWT signed with a different key should be rejected."""
        signing_key = _generate_rsa_key()
        different_key = _generate_rsa_key()
        jwk = _rsa_public_jwk(different_key)

        verifier = JWTTokenVerifier(
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            issuer="https://idp.example.com",
            audience="https://mcp.example.com",
        )

        claims = {
            "iss": "https://idp.example.com",
            "sub": "user-123",
            "aud": "https://mcp.example.com",
            "exp": int(time.time()) + 3600,
        }
        # Signed with signing_key, but JWKS has different_key.
        token = _sign_jwt(signing_key, claims)

        with unittest.mock.patch.object(
            verifier._jwks_client,
            "get_signing_key_from_jwt",
            return_value=pyjwt.PyJWK(jwk),
        ):
            result = await verifier.verify_token(token)

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

    @pytest.mark.anyio()
    async def test_accepts_active_token(self):
        """A token that the IdP reports as active should be accepted."""
        verifier = IntrospectionTokenVerifier(
            introspection_endpoint="https://idp.example.com/introspect",
            client_id="client",
            client_secret="secret",
        )

        mock_request = httpx.Request("POST", "https://idp.example.com/introspect")
        introspection_response = httpx.Response(
            200,
            json={
                "active": True,
                "client_id": "my-client",
                "scope": "read write",
                "exp": int(time.time()) + 3600,
            },
            request=mock_request,
        )

        with unittest.mock.patch(
            "token_verifier.httpx.AsyncClient.post",
            return_value=introspection_response,
        ):
            result = await verifier.verify_token("opaque-token-abc")

        assert result is not None
        assert result.client_id == "my-client"
        assert result.scopes == ["read", "write"]

    @pytest.mark.anyio()
    async def test_rejects_inactive_token(self):
        """A token that the IdP reports as inactive should be rejected."""
        verifier = IntrospectionTokenVerifier(
            introspection_endpoint="https://idp.example.com/introspect",
            client_id="client",
            client_secret="secret",
        )

        mock_request = httpx.Request("POST", "https://idp.example.com/introspect")
        introspection_response = httpx.Response(
            200,
            json={"active": False},
            request=mock_request,
        )

        with unittest.mock.patch(
            "token_verifier.httpx.AsyncClient.post",
            return_value=introspection_response,
        ):
            result = await verifier.verify_token("revoked-token")

        assert result is None

    @pytest.mark.anyio()
    async def test_rejects_expired_token(self):
        """A token with an expired timestamp should be rejected."""
        verifier = IntrospectionTokenVerifier(
            introspection_endpoint="https://idp.example.com/introspect",
            client_id="client",
            client_secret="secret",
        )

        mock_request = httpx.Request("POST", "https://idp.example.com/introspect")
        introspection_response = httpx.Response(
            200,
            json={
                "active": True,
                "client_id": "my-client",
                "exp": int(time.time()) - 3600,
            },
            request=mock_request,
        )

        with unittest.mock.patch(
            "token_verifier.httpx.AsyncClient.post",
            return_value=introspection_response,
        ):
            result = await verifier.verify_token("expired-token")

        assert result is None

    @pytest.mark.anyio()
    async def test_rejects_on_http_error(self):
        """An HTTP error from the introspection endpoint should reject the token."""
        verifier = IntrospectionTokenVerifier(
            introspection_endpoint="https://idp.example.com/introspect",
            client_id="client",
            client_secret="secret",
        )

        mock_request = httpx.Request("POST", "https://idp.example.com/introspect")
        error_response = httpx.Response(
            500,
            text="Internal Server Error",
            request=mock_request,
        )

        with unittest.mock.patch(
            "token_verifier.httpx.AsyncClient.post",
            return_value=error_response,
        ):
            result = await verifier.verify_token("some-token")

        assert result is None
