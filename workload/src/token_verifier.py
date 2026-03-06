# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.

"""Token verification for OAuth 2.1 resource server mode.

Supports two modes:
- JWT validation using the IdP's JWKS endpoint (for JWT access tokens)
- Token introspection via the IdP's introspection endpoint (for opaque tokens)
"""

from __future__ import annotations

import logging
import time

import httpx
import jwt as pyjwt
from mcp.server.auth.provider import AccessToken

logger = logging.getLogger(__name__)


def _parse_scopes(claims: dict) -> list[str]:
    """Extract scopes from token claims, handling both string and list formats."""
    scope = claims.get("scope", [])
    if isinstance(scope, str):
        return scope.split()
    return scope


class JWTTokenVerifier:
    """Verify JWT access tokens using the IdP's JWKS endpoint."""

    def __init__(
        self,
        jwks_uri: str,
        issuer: str,
        audience: str,
        *,
        jwks_cache_ttl: int = 300,
    ):
        self._jwks_uri = jwks_uri
        self._issuer = issuer
        self._audience = audience
        self._jwks_cache_ttl = jwks_cache_ttl
        self._jwks_client = pyjwt.PyJWKClient(
            jwks_uri, cache_jwk_set=True, lifespan=jwks_cache_ttl
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify a JWT and return an AccessToken if valid."""
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            claims = pyjwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                issuer=self._issuer,
                audience=self._audience,
                options={"require": ["exp", "iss", "sub"]},
            )
            return AccessToken(
                token=token,
                client_id=claims.get("client_id", claims.get("azp", claims.get("sub", ""))),
                scopes=_parse_scopes(claims),
                expires_at=claims.get("exp"),
            )
        except pyjwt.exceptions.PyJWTError:
            logger.debug("JWT verification failed", exc_info=True)
            return None


class IntrospectionTokenVerifier:
    """Verify opaque tokens via the IdP's introspection endpoint (RFC 7662)."""

    def __init__(
        self,
        introspection_endpoint: str,
        client_id: str,
        client_secret: str,
    ):
        self._introspection_endpoint = introspection_endpoint
        self._client_id = client_id
        self._client_secret = client_secret

    async def verify_token(self, token: str) -> AccessToken | None:
        """Introspect a token and return an AccessToken if active."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._introspection_endpoint,
                    data={"token": token, "token_type_hint": "access_token"},
                    auth=(self._client_id, self._client_secret),
                )
                response.raise_for_status()
                data = response.json()

            if not data.get("active", False):
                return None

            # Check expiry if present.
            exp = data.get("exp")
            if exp and time.time() > exp:
                return None

            scope_value = data.get("scope", "")
            scopes = scope_value.split() if isinstance(scope_value, str) else scope_value

            return AccessToken(
                token=token,
                client_id=data.get("client_id", ""),
                scopes=scopes,
                expires_at=exp,
            )
        except (httpx.HTTPError, KeyError, ValueError):
            logger.debug("Token introspection failed", exc_info=True)
            return None


def create_token_verifier(
    issuer_url: str,
    resource_server_url: str,
    jwks_uri: str | None = None,
    introspection_endpoint: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    jwt_access_tokens: bool = True,
) -> JWTTokenVerifier | IntrospectionTokenVerifier:
    """Create the appropriate token verifier based on available configuration."""
    if jwt_access_tokens and jwks_uri:
        return JWTTokenVerifier(
            jwks_uri=jwks_uri,
            issuer=issuer_url,
            audience=resource_server_url,
        )
    elif introspection_endpoint and client_id and client_secret:
        return IntrospectionTokenVerifier(
            introspection_endpoint=introspection_endpoint,
            client_id=client_id,
            client_secret=client_secret,
        )
    else:
        msg = (
            "OAuth configuration incomplete: need either jwks_uri "
            "(for JWT validation) or introspection_endpoint + client credentials "
            "(for opaque token validation)"
        )
        raise ValueError(msg)
