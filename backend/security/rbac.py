"""Role-Based Access Control (RBAC) for enterprise endpoints."""

import os
import logging
from typing import List, Set, Optional
from enum import Enum
from functools import wraps

from fastapi import HTTPException

from backend.security.auth import TenantContext

logger = logging.getLogger(__name__)


class Role(str, Enum):
    """User roles."""

    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class RBACConfig:
    """RBAC configuration."""

    def __init__(self):
        self.enabled = os.getenv("RBAC_ENABLED", "false").lower() == "true"
        self.default_role = os.getenv("DEFAULT_ROLE", "viewer")

        # Role permissions
        self.admin_roles: Set[str] = set(os.getenv("ADMIN_ROLES", "admin").split(","))
        self.editor_roles: Set[str] = set(
            os.getenv("EDITOR_ROLES", "admin,editor").split(",")
        )
        self.viewer_roles: Set[str] = set(
            os.getenv("VIEWER_ROLES", "admin,editor,viewer").split(",")
        )

        # Permission matrix
        self.permissions = {
            Role.ADMIN: {"create", "read", "update", "delete", "reindex", "manage_users"},
            Role.EDITOR: {"create", "read", "update", "delete"},
            Role.VIEWER: {"read"},
        }

        logger.info(f"RBACConfig initialized (enabled={self.enabled})")


class RBACEnforcer:
    """RBAC permission enforcer."""

    def __init__(self, config: Optional[RBACConfig] = None):
        self.config = config or RBACConfig()

    def has_role(self, role: str, required_roles: List[str]) -> bool:
        """Check if user has one of required roles.

        Args:
            role: User's role
            required_roles: List of allowed roles

        Returns:
            True if role in required_roles
        """
        return role in required_roles

    def has_permission(self, role: str, action: str) -> bool:
        """Check if user role can perform action.

        Args:
            role: User's role
            action: Action to perform (create, read, update, delete, etc.)

        Returns:
            True if role has permission
        """
        role_enum = Role(role) if isinstance(role, str) else role
        permissions = self.config.permissions.get(role_enum, set())
        return action in permissions

    def check_permission(
        self, role: str, action: str, raise_on_denied: bool = True
    ) -> bool:
        """Check permission and optionally raise.

        Args:
            role: User's role
            action: Action to check
            raise_on_denied: Raise 403 if denied

        Returns:
            True if authorized

        Raises:
            HTTPException(403) if denied and raise_on_denied=True
        """
        has_perm = self.has_permission(role, action)

        if not has_perm and raise_on_denied:
            logger.warning(f"RBAC denied: role={role}, action={action}")
            raise HTTPException(status_code=403, detail="Forbidden")

        return has_perm


def require_role(*required_roles: str):
    """Decorator to require specific roles.

    Args:
        *required_roles: Roles allowed to access endpoint

    Usage:
        @require_role("admin")
        async def admin_endpoint(request: Request):
            pass

        @require_role("admin", "editor")
        async def edit_endpoint(request: Request):
            pass
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Check if RBAC enabled
            config = RBACConfig()
            if not config.enabled:
                logger.debug("RBAC disabled, allowing access")
                return await func(*args, **kwargs)

            # Get current role
            current_role = TenantContext.get_current_role()

            # Check authorization
            if current_role not in required_roles:
                logger.warning(
                    f"RBAC denied: role={current_role}, "
                    f"required={required_roles}, endpoint={func.__name__}"
                )
                raise HTTPException(status_code=403, detail="Forbidden")

            logger.debug(f"RBAC allowed: role={current_role}, endpoint={func.__name__}")

            # Call original function
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_permission(action: str):
    """Decorator to require specific permission/action.

    Args:
        action: Action to require (create, read, update, delete, etc.)

    Usage:
        @require_permission("delete")
        async def delete_endpoint(request: Request):
            pass
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Check if RBAC enabled
            config = RBACConfig()
            if not config.enabled:
                logger.debug("RBAC disabled, allowing access")
                return await func(*args, **kwargs)

            # Get current role
            current_role = TenantContext.get_current_role()

            # Check permission
            enforcer = RBACEnforcer(config)
            if not enforcer.has_permission(current_role, action):
                logger.warning(
                    f"Permission denied: role={current_role}, "
                    f"action={action}, endpoint={func.__name__}"
                )
                raise HTTPException(status_code=403, detail="Forbidden")

            logger.debug(f"Permission allowed: role={current_role}, action={action}")

            # Call original function
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def get_rbac_enforcer() -> RBACEnforcer:
    """Get singleton RBAC enforcer."""
    return RBACEnforcer()
