"""JWT authentication and tenant context management."""

import os
import logging
from typing import Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import threading

import jwt

logger = logging.getLogger(__name__)


@dataclass
class JWTPayload:
    """Parsed JWT payload."""

    tenant_id: str
    user_id: Optional[str] = None
    user_role: str = "viewer"  # admin, editor, viewer
    exp: Optional[int] = None
    iat: Optional[int] = None
    jti: Optional[str] = None  # JWT ID for revocation


class JWTConfig:
    """JWT configuration."""

    def __init__(self):
        self.enabled = os.getenv("AUTH_ENABLED", "false").lower() == "true"
        self.secret_key = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
        self.algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.expiry_seconds = int(os.getenv("JWT_EXPIRY_SECONDS", "3600"))
        self.require_auth = os.getenv("REQUIRE_AUTH", "false").lower() == "true"

        if self.enabled and self.secret_key == "your-secret-key-change-in-production":
            logger.warning("JWT_SECRET_KEY using default value, set in production!")

        logger.info(
            f"JWTConfig initialized (enabled={self.enabled}, "
            f"require_auth={self.require_auth}, expiry={self.expiry_seconds}s)"
        )


class TokenValidator:
    """JWT token validation."""

    def __init__(self, config: Optional[JWTConfig] = None):
        self.config = config or JWTConfig()

    def validate(self, token: str) -> Optional[JWTPayload]:
        """Validate JWT token and extract payload.

        Args:
            token: JWT token string

        Returns:
            JWTPayload if valid, None if invalid
        """
        if not self.config.enabled:
            logger.debug("Auth disabled, skipping token validation")
            return None

        if not token:
            logger.debug("No token provided")
            return None

        try:
            # Remove "Bearer " prefix if present
            if token.startswith("Bearer "):
                token = token[7:]

            payload = jwt.decode(
                token,
                self.config.secret_key,
                algorithms=[self.config.algorithm],
            )

            # Extract required fields
            tenant_id = payload.get("tenant_id")
            if not tenant_id:
                logger.warning("Token missing tenant_id")
                return None

            return JWTPayload(
                tenant_id=tenant_id,
                user_id=payload.get("user_id"),
                user_role=payload.get("user_role", "viewer"),
                exp=payload.get("exp"),
                iat=payload.get("iat"),
                jti=payload.get("jti"),
            )

        except jwt.ExpiredSignatureError:
            logger.debug("Token expired")
            return None

        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None

        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return None

    def issue_token(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
        user_role: str = "viewer",
        ttl_seconds: Optional[int] = None,
    ) -> str:
        """Issue a new JWT token.

        Args:
            tenant_id: Tenant identifier
            user_id: Optional user identifier
            user_role: User role (admin, editor, viewer)
            ttl_seconds: Time-to-live (None = use config default)

        Returns:
            JWT token string
        """
        ttl = ttl_seconds or self.config.expiry_seconds
        now = datetime.utcnow()
        exp = now + timedelta(seconds=ttl)

        payload = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "user_role": user_role,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "jti": f"{tenant_id}_{user_id}_{int(now.timestamp())}",
        }

        token = jwt.encode(
            payload,
            self.config.secret_key,
            algorithm=self.config.algorithm,
        )

        logger.info(f"Issued token for tenant={tenant_id}, user={user_id}, role={user_role}")

        return token


class TenantContext:
    """Thread-local tenant context storage."""

    _local = threading.local()

    @classmethod
    def set_context(cls, payload: JWTPayload) -> None:
        """Set current tenant context.

        Args:
            payload: JWTPayload to store
        """
        cls._local.payload = payload
        logger.debug(f"Set context: tenant={payload.tenant_id}, role={payload.user_role}")

    @classmethod
    def get_current_payload(cls) -> Optional[JWTPayload]:
        """Get current JWT payload.

        Returns:
            JWTPayload or None if not set
        """
        return getattr(cls._local, "payload", None)

    @classmethod
    def get_current_tenant(cls) -> str:
        """Get current tenant ID.

        Returns:
            Tenant ID or "default" if not set
        """
        payload = cls.get_current_payload()
        return payload.tenant_id if payload else "default"

    @classmethod
    def get_current_user(cls) -> Optional[str]:
        """Get current user ID.

        Returns:
            User ID or None
        """
        payload = cls.get_current_payload()
        return payload.user_id if payload else None

    @classmethod
    def get_current_role(cls) -> str:
        """Get current user role.

        Returns:
            Role or "viewer" if not set
        """
        payload = cls.get_current_payload()
        return payload.user_role if payload else "viewer"

    @classmethod
    def clear_context(cls) -> None:
        """Clear context (for testing)."""
        if hasattr(cls._local, "payload"):
            delattr(cls._local, "payload")


def get_token_validator() -> TokenValidator:
    """Get singleton token validator."""
    return TokenValidator()
