"""Multi-tenant data isolation and filtering."""

import logging
from typing import Optional

from backend.security.auth import TenantContext
from backend.schemas.retrieval import SearchRequest

logger = logging.getLogger(__name__)


class TenantFilter:
    """Transparent tenant filtering for queries."""

    @staticmethod
    def apply_to_request(request: SearchRequest) -> SearchRequest:
        """Apply tenant filtering to search request.

        Args:
            request: Original SearchRequest

        Returns:
            Request with tenant_id injected
        """
        tenant_id = TenantContext.get_current_tenant()
        request.tenant_id = tenant_id
        logger.debug(f"Applied tenant filter: {tenant_id}")
        return request

    @staticmethod
    def apply_to_query(query_filter: dict) -> dict:
        """Apply tenant filtering to Qdrant query filter.

        Args:
            query_filter: Original filter dict

        Returns:
            Filter with tenant_id condition
        """
        tenant_id = TenantContext.get_current_tenant()

        # Add tenant condition
        if query_filter:
            return {
                "must": [
                    query_filter,
                    {"key": "tenant_id", "match": {"value": tenant_id}},
                ]
            }
        else:
            return {"key": "tenant_id", "match": {"value": tenant_id}}

    @staticmethod
    def scope_document_id(document_id: str) -> str:
        """Scope document ID to tenant.

        Args:
            document_id: Original document ID

        Returns:
            Tenant-scoped document ID
        """
        tenant_id = TenantContext.get_current_tenant()
        return f"{tenant_id}:{document_id}"

    @staticmethod
    def unscope_document_id(scoped_id: str) -> str:
        """Extract original document ID from scoped ID.

        Args:
            scoped_id: Tenant-scoped document ID

        Returns:
            Original document ID
        """
        parts = scoped_id.split(":", 1)
        return parts[1] if len(parts) > 1 else scoped_id


class TenantContextDependency:
    """FastAPI dependency for tenant filtering.

    Usage:
        @router.post("/search")
        async def search(
            request: SearchRequest,
            _ = Depends(TenantContextDependency()),
        ):
            # request.tenant_id now set to current tenant
            pass
    """

    def __call__(self, request: SearchRequest) -> SearchRequest:
        """Inject tenant_id into request."""
        return TenantFilter.apply_to_request(request)


def get_tenant_filter() -> TenantFilter:
    """Get tenant filter utility."""
    return TenantFilter()
