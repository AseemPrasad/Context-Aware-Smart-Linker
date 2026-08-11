"""Token lifecycle management: refresh and revocation."""

import logging
import redis
import os
from typing import Optional

from backend.security.auth import TokenValidator, JWTPayload, JWTConfig

logger = logging.getLogger(__name__)


class TokenManager:
    """Manage token lifecycle: issue, refresh, revoke."""

    def __init__(self):
        self.config = JWTConfig()
        self.validator = TokenValidator()
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info("Token manager connected to Redis")
        except Exception as e:
            logger.warning(f"Redis unavailable for revocation list: {e}")
            self.redis_client = None

    def issue_token(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
        user_role: str = "viewer",
    ) -> str:
        """Issue new JWT token.

        Args:
            tenant_id: Tenant ID
            user_id: Optional user ID
            user_role: User role

        Returns:
            JWT token string
        """
        return self.validator.issue_token(
            tenant_id=tenant_id,
            user_id=user_id,
            user_role=user_role,
        )

    def refresh_token(self, old_token: str) -> Optional[str]:
        """Refresh token by validating and issuing new one.

        Args:
            old_token: Existing JWT token

        Returns:
            New JWT token or None if invalid
        """
        # Validate old token
        payload = self.validator.validate(old_token)

        if not payload:
            logger.warning("Invalid token for refresh")
            return None

        # Revoke old token
        if payload.jti:
            self.revoke_token(old_token, payload.jti)

        # Issue new token
        new_token = self.validator.issue_token(
            tenant_id=payload.tenant_id,
            user_id=payload.user_id,
            user_role=payload.user_role,
        )

        logger.info(f"Token refreshed for tenant={payload.tenant_id}")

        return new_token

    def revoke_token(self, token: str, jti: Optional[str] = None) -> bool:
        """Revoke JWT token (add to revocation list).

        Args:
            token: JWT token string
            jti: Token ID (extracted if not provided)

        Returns:
            True if revoked successfully
        """
        if not self.redis_client:
            logger.warning("Redis unavailable for token revocation")
            return False

        try:
            # Extract JTI if not provided
            if not jti:
                payload = self.validator.validate(token)
                if not payload or not payload.jti:
                    logger.warning("Cannot extract JTI for revocation")
                    return False
                jti = payload.jti

            # Add to revocation list with TTL = token expiry
            payload = self.validator.validate(token)
            ttl = (payload.exp - payload.iat) if payload and payload.exp and payload.iat else 3600

            self.redis_client.set(f"revoked_token:{jti}", "1", ex=ttl)

            logger.info(f"Token revoked: jti={jti}")

            return True

        except Exception as e:
            logger.error(f"Error revoking token: {e}")
            return False

    def is_revoked(self, jti: str) -> bool:
        """Check if token is revoked.

        Args:
            jti: Token ID

        Returns:
            True if token is revoked
        """
        if not self.redis_client:
            return False

        try:
            exists = self.redis_client.exists(f"revoked_token:{jti}")
            return bool(exists)

        except Exception as e:
            logger.error(f"Error checking revocation: {e}")
            return False


def get_token_manager() -> TokenManager:
    """Get singleton token manager."""
    return TokenManager()
