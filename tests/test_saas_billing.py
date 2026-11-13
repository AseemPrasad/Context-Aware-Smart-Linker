"""Automated tests for B2B SaaS billing, credit burn rates, and quota enforcement."""

import unittest
from backend.billing.meter import UsageMeter
from backend.billing.models import PlanTier


class TestSaaSBillingAndQuotas(unittest.TestCase):
    def setUp(self):
        self.meter = UsageMeter()

    def test_credit_deduction_and_quota_block(self):
        tenant_id = "test_hedge_fund"
        # Provision starter tier with 10 credits for fast testing
        sub = self.meter.get_or_create_tenant(tenant_id, plan=PlanTier.STARTER)
        sub.monthly_credits_quota = 5

        # Deduct 3 credits
        res1 = self.meter.deduct_credits(tenant_id, operation_cost=3)
        self.assertTrue(res1.allowed)
        self.assertEqual(res1.credits_consumed, 3)
        self.assertEqual(res1.credits_remaining, 2)

        # Deduct 2 credits (now at quota 5/5)
        res2 = self.meter.deduct_credits(tenant_id, operation_cost=2)
        self.assertTrue(res2.allowed)
        self.assertEqual(res2.credits_remaining, 0)

        # 6th credit should be strictly blocked by hard cap
        res3 = self.meter.deduct_credits(tenant_id, operation_cost=1)
        self.assertFalse(res3.allowed)
        self.assertIn("exceeded", res3.error_message)

    def test_cache_hits_consume_zero_credits(self):
        tenant_id = "test_law_firm"
        self.meter.get_or_create_tenant(tenant_id, plan=PlanTier.STARTER)

        # Cache hit deduction
        res = self.meter.deduct_credits(tenant_id, operation_cost=1, is_cache_hit=True)
        self.assertTrue(res.allowed)
        self.assertEqual(res.credits_consumed, 0)

        summary = self.meter.get_usage_summary(tenant_id)
        self.assertEqual(summary.credits_used, 0)

    def test_plan_upgrade_expands_quota(self):
        tenant_id = "growth_fund"
        sub = self.meter.get_or_create_tenant(tenant_id, plan=PlanTier.STARTER)
        self.assertEqual(sub.monthly_credits_quota, 500)

        # Upgrade to Professional
        sub.plan = PlanTier.PROFESSIONAL
        sub.monthly_credits_quota = 5000
        sub.seats_allocated = 10

        summary = self.meter.get_usage_summary(tenant_id)
        self.assertEqual(summary.plan, PlanTier.PROFESSIONAL)
        self.assertEqual(summary.credits_quota, 5000)
        self.assertEqual(summary.seats_allocated, 10)


if __name__ == "__main__":
    unittest.main()

