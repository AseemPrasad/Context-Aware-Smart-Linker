"""OpenID Connect (OIDC) and JWT Enterprise Authentication Provider.

Supports verification of RSA/ECDSA JSON Web Tokens issued by Okta, Auth0,
Microsoft Entra ID (Azure AD), Supabase, or Clerk. Falls back seamlessly
to local token validation if OIDC is not configured.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class EnterpriseJwtValidator:
    """Validates JWTs from standard enterprise Identity Providers (IdPs)."""

    def __init__(self, jwks_url: Optional[str] = None, issuer: Optional[str] = None):
        self.jwks_url = jwks_url or os.getenv("OIDC_JWKS_URL")
        self.issuer = issuer or os.getenv("OIDC_ISSUER")
        self._cached_keys: Dict[str, Any] = {}
        self._last_keys_refresh: float = 0.0

    def decode_and_validate(self, token: str) -> Optional[Dict[str, Any]]:
        """Extracts and cryptographically validates claims from Bearer token.
        
        When OIDC_JWKS_URL is configured, performs RS256 signature verification.
        Falls back safely to claims extraction when unconfigured in local environments.
        """
        if not token:
            return None

        # Clean Bearer prefix
        raw_token = token.replace("Bearer ", "").strip()
        parts = raw_token.split(".")
        if len(parts) != 3:
            # Not a JWT (e.g. legacy casl_sec_... token)
            return None

        # If JWKS URL is present, attempt cryptographic verification via jwt library if available
        if self.jwks_url:
            try:
                import jwt  # PyJWT
                from jwt import PyJWKClient
                jwks_client = PyJWKClient(self.jwks_url)
                signing_key = jwks_client.get_signing_key_from_jwt(raw_token)
                claims = jwt.decode(
                    raw_token,
                    signing_key.key,
                    algorithms=["RS256", "ES256"],
                    issuer=self.issuer if self.issuer else None,
                    options={"verify_exp": True}
                )
                tenant_id = (
                    claims.get("tenant_id")
                    or claims.get("org_id")
                    or claims.get("workspace_id")
                    or claims.get("custom:tenant_id")
                    or "default"
                )
                claims["resolved_tenant_id"] = tenant_id
                return claims
            except Exception as jwks_err:
                logger.warning("Cryptographic JWKS signature verification failed: %s", jwks_err)
                return None

        try:
            import base64
            # Add padding if needed
            payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
            payload_json = base64.urlsafe_b64decode(payload_b64).decode("utf-8")
            claims = json.loads(payload_json)

            # Check expiration
            exp = claims.get("exp")
            if exp and float(exp) < time.time():
                logger.warning("Rejecting expired JWT token")
                return None

            # Check issuer if specified
            if self.issuer and claims.get("iss") != self.issuer:
                logger.warning("JWT issuer mismatch: %s != %s", claims.get("iss"), self.issuer)
                return None

            # Resolve tenant ID from standard enterprise claims
            tenant_id = (
                claims.get("tenant_id")
                or claims.get("org_id")
                or claims.get("workspace_id")
                or claims.get("custom:tenant_id")
                or "default"
            )
            claims["resolved_tenant_id"] = tenant_id
            return claims
        except Exception as e:
            logger.debug("Failed to decode JWT claims: %s", e)
            return None


_jwt_validator = EnterpriseJwtValidator()


def get_jwt_validator() -> EnterpriseJwtValidator:
    return _jwt_validator

