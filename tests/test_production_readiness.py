"""Production readiness verification test suite.

Validates:
1. RedisUsageMeter fallback and atomic credit accounting.
2. SecDocumentFetcher clean HTML and section extraction.
3. EnterpriseJwtValidator OIDC claim extraction and expired token rejection.
4. RemoteAPIEncoder graceful fallback.
"""

import unittest
from backend.billing.models import PlanTier
from backend.billing.redis_meter import RedisUsageMeter
from backend.tasks.sec_document_fetcher import SecDocumentFetcher
from backend.security.jwt_auth import EnterpriseJwtValidator
from backend.core.remote_encoder import RemoteAPIEncoder


class TestProductionReadiness(unittest.TestCase):

    def test_redis_meter_in_memory_fallback(self):
        # Point to unreachable port to test seamless in-memory fallback
        meter = RedisUsageMeter(redis_url="redis://localhost:9999/0")
        sub = meter.get_or_create_tenant("hedge_fund_xyz", plan=PlanTier.PROFESSIONAL)
        self.assertEqual(sub.monthly_credits_quota, 5000)

        # Deduct credit
        result = meter.deduct_credits("hedge_fund_xyz", operation_cost=5)
        self.assertTrue(result.allowed)
        self.assertEqual(result.credits_remaining, 4995)

    def test_sec_document_fetcher_cleaning(self):
        raw_sec_html = """
        <html>
            <head><style>.text { color: red; }</style></head>
            <body>
                <script>var x = 10;</script>
                <h1>Form 10-K</h1>
                <div>Item 1A. Risk Factors</div>
                <p>The company faces material cybersecurity risks and debt covenant constraints.</p>
                <div>Item 1B. Unresolved Staff Comments</div>
            </body>
        </html>
        """
        cleaned = SecDocumentFetcher.clean_html(raw_sec_html)
        self.assertNotIn("<script>", cleaned)
        self.assertNotIn("var x = 10;", cleaned)
        self.assertIn("Item 1A. Risk Factors", cleaned)
        self.assertIn("cybersecurity risks", cleaned)

        sections = SecDocumentFetcher.extract_key_sections(cleaned)
        self.assertIn("Item 1A - Risk Factors", sections)
        self.assertIn("cybersecurity risks", sections["Item 1A - Risk Factors"])

    def test_enterprise_jwt_claim_extraction(self):
        import base64
        import json
        import time

        validator = EnterpriseJwtValidator()

        # Valid payload
        payload = {
            "sub": "user_42",
            "org_id": "kirkland_ellis",
            "exp": time.time() + 3600,
            "role": "admin"
        }
        b64_header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode("utf-8").rstrip("=")
        b64_payload = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
        fake_jwt = f"{b64_header}.{b64_payload}."

        claims = validator.decode_and_validate(fake_jwt)
        self.assertIsNotNone(claims)
        self.assertEqual(claims["resolved_tenant_id"], "kirkland_ellis")

        # Expired token
        expired_payload = {
            "sub": "user_42",
            "exp": time.time() - 3600,
        }
        b64_expired = base64.urlsafe_b64encode(json.dumps(expired_payload).encode("utf-8")).decode("utf-8").rstrip("=")
        expired_jwt = f"{b64_header}.{b64_expired}."
        self.assertIsNone(validator.decode_and_validate(expired_jwt))

    def test_remote_encoder_resilience(self):
        # Point to unreachable URL to verify deterministic fallback
        encoder = RemoteAPIEncoder(api_url="http://localhost:9999", dimension=384)
        vectors = encoder.encode(["Term 1", "Term 2"])
        self.assertEqual(len(vectors), 2)
        self.assertEqual(len(vectors[0]), 384)


if __name__ == "__main__":
    unittest.main()

