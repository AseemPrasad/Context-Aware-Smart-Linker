"""Audit trail and security event logging."""

import logging
import json
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("audit")


class SecurityEventType(str, Enum):
    """Security event types."""

    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    RBAC_DENIED = "rbac_denied"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    CROSS_TENANT_ACCESS = "cross_tenant_access"
    TOKEN_REVOKED = "token_revoked"
    TOKEN_REFRESHED = "token_refreshed"


@dataclass
class SecurityEvent:
    """Security event for audit trail."""

    event_type: SecurityEventType
    tenant_id: str
    user_id: Optional[str]
    user_role: Optional[str]
    endpoint: str
    method: str
    status_code: int
    message: str
    timestamp: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "event_type": self.event_type.value,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "user_role": self.user_role,
            "endpoint": self.endpoint,
            "method": self.method,
            "status_code": self.status_code,
            "message": self.message,
            "timestamp": self.timestamp,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }


class AuditLogger:
    """Log security events."""

    def __init__(self):
        self.failure_counts = {}  # Track auth failures per tenant
        self.failure_threshold = 5
        self.failure_window = 300  # 5 minutes

    def log_event(self, event: SecurityEvent) -> None:
        """Log a security event.

        Args:
            event: SecurityEvent to log
        """
        # Log as structured JSON
        audit_logger.info(json.dumps(event.to_dict()))

        # Check for patterns
        self._check_anomalies(event)

    def log_auth_event(
        self,
        tenant_id: str,
        user_id: Optional[str],
        user_role: Optional[str],
        success: bool,
        endpoint: str = "/auth/token",
        ip_address: Optional[str] = None,
    ) -> None:
        """Log authentication event.

        Args:
            tenant_id: Tenant ID
            user_id: User ID
            user_role: User role
            success: Whether auth succeeded
            endpoint: Auth endpoint
            ip_address: Client IP
        """
        event_type = SecurityEventType.AUTH_SUCCESS if success else SecurityEventType.AUTH_FAILURE

        event = SecurityEvent(
            event_type=event_type,
            tenant_id=tenant_id,
            user_id=user_id,
            user_role=user_role,
            endpoint=endpoint,
            method="POST",
            status_code=200 if success else 401,
            message="Authentication successful" if success else "Authentication failed",
            timestamp=datetime.utcnow().isoformat(),
            ip_address=ip_address,
        )

        self.log_event(event)

        # Track failures
        if not success:
            key = f"{tenant_id}:{user_id}"
            self.failure_counts[key] = self.failure_counts.get(key, 0) + 1

            if self.failure_counts[key] >= self.failure_threshold:
                logger.critical(
                    f"Repeated auth failures: {key} ({self.failure_counts[key]} attempts)"
                )

    def log_rbac_event(
        self,
        tenant_id: str,
        user_id: Optional[str],
        user_role: str,
        action: str,
        authorized: bool,
        endpoint: str,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log RBAC decision.

        Args:
            tenant_id: Tenant ID
            user_id: User ID
            user_role: User role
            action: Action attempted
            authorized: Whether authorized
            endpoint: Endpoint accessed
            ip_address: Client IP
        """
        if not authorized:
            event = SecurityEvent(
                event_type=SecurityEventType.RBAC_DENIED,
                tenant_id=tenant_id,
                user_id=user_id,
                user_role=user_role,
                endpoint=endpoint,
                method="POST",  # Usually mutation operations
                status_code=403,
                message=f"RBAC denied: action={action}",
                timestamp=datetime.utcnow().isoformat(),
                ip_address=ip_address,
            )

            self.log_event(event)

    def log_rate_limit_event(
        self,
        tenant_id: str,
        endpoint: str,
        reset_seconds: int,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log rate limit exceeded event.

        Args:
            tenant_id: Tenant ID
            endpoint: Endpoint hit
            reset_seconds: Seconds until reset
            ip_address: Client IP
        """
        event = SecurityEvent(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
            tenant_id=tenant_id,
            user_id=None,
            user_role=None,
            endpoint=endpoint,
            method="ANY",
            status_code=429,
            message=f"Rate limit exceeded, reset in {reset_seconds}s",
            timestamp=datetime.utcnow().isoformat(),
            ip_address=ip_address,
        )

        self.log_event(event)

    def _check_anomalies(self, event: SecurityEvent) -> None:
        """Check for anomalous patterns.

        Args:
            event: Event to check
        """
        # Check for high rate limit events
        if event.event_type == SecurityEventType.RATE_LIMIT_EXCEEDED:
            key = f"ratelimit:{event.tenant_id}"
            count = self.failure_counts.get(key, 0) + 1
            self.failure_counts[key] = count

            if count > 10:
                logger.warning(f"High rate limit events: {event.tenant_id} ({count} events)")


def get_audit_logger() -> AuditLogger:
    """Get singleton audit logger."""
    return AuditLogger()
