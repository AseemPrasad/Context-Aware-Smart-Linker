"""Integration and End-to-End API tests for CASL backend."""

import asyncio
import unittest
import httpx
from backend.main import app


class TestApiIntegration(unittest.TestCase):
    def setUp(self):
        self.transport = httpx.ASGITransport(app=app)

    def test_health_endpoint(self):
        """Verify root health check probe."""
        async def _run():
            async with httpx.AsyncClient(transport=self.transport, base_url="http://test") as client:
                res = await client.get("/health")
                self.assertEqual(res.status_code, 200)
                self.assertEqual(res.json(), {"status": "ok"})
        asyncio.run(_run())

    def test_cache_stats_endpoint(self):
        """Verify cache monitor statistics probe."""
        async def _run():
            async with httpx.AsyncClient(transport=self.transport, base_url="http://test") as client:
                res = await client.get("/cache/stats")
                self.assertEqual(res.status_code, 200)
                self.assertIn("enabled", res.json())
        asyncio.run(_run())

    def test_finance_health_endpoint(self):
        """Verify domain-specific finance router health probe."""
        async def _run():
            async with httpx.AsyncClient(transport=self.transport, base_url="http://test") as client:
                res = await client.get("/api/v1/finance/health")
                self.assertEqual(res.status_code, 200)
                self.assertEqual(res.json().get("module"), "finance_due_diligence")
        asyncio.run(_run())

    def test_finance_explain_e2e(self):
        """End-to-end integration test of /api/v1/finance/explain."""
        payload = {
            "term": "EBITDA Margin",
            "surrounding_context": "Company experienced significant EBITDA margin expansion due to compute infrastructure efficiencies.",
            "page_title": "NVDA Q3 FY2025 Earnings Disclosure",
            "ticker": "NVDA",
            "tenant_id": "test_tenant",
            "strict_citations": True
        }
        async def _run():
            async with httpx.AsyncClient(transport=self.transport, base_url="http://test") as client:
                res = await client.post("/api/v1/finance/explain", json=payload)
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertEqual(data["term"], "EBITDA Margin")
                self.assertIn("executive_summary", data)
                self.assertIsInstance(data["citations"], list)
                self.assertGreaterEqual(data["confidence_score"], 0.0)
                self.assertLessEqual(data["confidence_score"], 1.0)
        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
