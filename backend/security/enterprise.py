"""Enterprise tenant tiers and quotas."""

import os
import logging
from typing import Optional, Dict
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class TenantTier(str, Enum):
    """Tenant pricing tiers."""

    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


@dataclass
class TenantQuota:
    """Quota limits for a tenant."""

    rate_limit_req_per_min: int
    max_documents: int
    max_concurrent_searches: int
    features_enabled: list  # List of feature flags


class TenantManager:
    """Manage tenant tiers and quotas."""

    # Tier definitions
    TIER_DEFAULTS = {
        TenantTier.FREE: {
            "rate_limit_req_per_min": 60,
            "max_documents": 1000,
            "max_concurrent_searches": 1,
            "features_enabled": ["basic_search"],
        },
        TenantTier.PRO: {
            "rate_limit_req_per_min": 1000,
            "max_documents": 100000,
            "max_concurrent_searches": 10,
            "features_enabled": ["basic_search", "agents"],
        },
        TenantTier.ENTERPRISE: {
            "rate_limit_req_per_min": 5000,
            "max_documents": 1000000,
            "max_concurrent_searches": 100,
            "features_enabled": ["basic_search", "agents", "evals", "auto_rerank"],
        },
    }

    def __init__(self):
        self.default_tier = os.getenv("DEFAULT_TIER", TenantTier.FREE)
        self.tenant_tiers: Dict[str, TenantTier] = {}
        self.custom_quotas: Dict[str, TenantQuota] = {}

        logger.info(f"TenantManager initialized (default_tier={self.default_tier})")

    def get_tenant_tier(self, tenant_id: str) -> TenantTier:
        """Get tier for tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            TenantTier enum value
        """
        # Check cache
        if tenant_id in self.tenant_tiers:
            return self.tenant_tiers[tenant_id]

        # Check environment
        env_key = f"TENANT_TIER_{tenant_id.upper()}"
        tier_str = os.getenv(env_key, self.default_tier)

        try:
            tier = TenantTier(tier_str)
            self.tenant_tiers[tenant_id] = tier
            return tier
        except ValueError:
            logger.warning(f"Invalid tier for {tenant_id}: {tier_str}, using default")
            return TenantTier(self.default_tier)

    def get_quota(self, tenant_id: str) -> TenantQuota:
        """Get quota for tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            TenantQuota with limits
        """
        # Check custom override
        if tenant_id in self.custom_quotas:
            return self.custom_quotas[tenant_id]

        # Get tier
        tier = self.get_tenant_tier(tenant_id)

        # Create quota from tier defaults
        tier_config = self.TIER_DEFAULTS[tier]

        return TenantQuota(
            rate_limit_req_per_min=tier_config["rate_limit_req_per_min"],
            max_documents=tier_config["max_documents"],
            max_concurrent_searches=tier_config["max_concurrent_searches"],
            features_enabled=tier_config["features_enabled"],
        )

    def check_feature_access(self, tenant_id: str, feature: str) -> bool:
        """Check if tenant has access to feature.

        Args:
            tenant_id: Tenant identifier
            feature: Feature name

        Returns:
            True if feature enabled
        """
        quota = self.get_quota(tenant_id)
        has_access = feature in quota.features_enabled

        if not has_access:
            logger.warning(f"Feature access denied: tenant={tenant_id}, feature={feature}")

        return has_access

    def set_custom_quota(self, tenant_id: str, quota: TenantQuota) -> None:
        """Set custom quota for tenant.

        Args:
            tenant_id: Tenant identifier
            quota: Custom quota
        """
        self.custom_quotas[tenant_id] = quota
        logger.info(f"Set custom quota for {tenant_id}")

    def set_tenant_tier(self, tenant_id: str, tier: TenantTier) -> None:
        """Set tier for tenant.

        Args:
            tenant_id: Tenant identifier
            tier: TenantTier enum value
        """
        self.tenant_tiers[tenant_id] = tier
        # Clear cached quota so it's regenerated
        if tenant_id in self.custom_quotas:
            del self.custom_quotas[tenant_id]
        logger.info(f"Set tier for {tenant_id}: {tier}")


def get_tenant_manager() -> TenantManager:
    """Get singleton tenant manager."""
    return TenantManager()
