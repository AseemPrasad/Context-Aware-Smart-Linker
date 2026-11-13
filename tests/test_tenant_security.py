"""Multi-tenant isolation and data boundary tests."""

import unittest
from backend.db.vector_store import VectorStore
from backend.schemas.retrieval import IngestRequest, SearchRequest
from backend.tasks.sec_edgar_pipeline import SecEdgarPipeline


class TestTenantIsolationAndSecPipeline(unittest.TestCase):
    def setUp(self):
        self.store = VectorStore()
        self.pipeline = SecEdgarPipeline(store=self.store)

    def test_tenant_boundary_isolation(self):
        """Asserts that queries under Tenant A never return data owned by Tenant B."""
        # Ingest private document for Tenant A
        req_a = IngestRequest(
            document_id="deal_doc_a",
            text="Confidential merger terms for Project Titan with 45% premium.",
            tenant_id="hedge_fund_alpha",
            metadata={"deal_name": "Project Titan", "passage": "Confidential merger terms for Project Titan with 45% premium."}
        )
        self.store.ingest(req_a, embeddings=[[1.0, 0.0, 0.0]])

        # Ingest private document for Tenant B
        req_b = IngestRequest(
            document_id="deal_doc_b",
            text="Project Pegasus restructuring plan and debt recapitalization.",
            tenant_id="hedge_fund_beta",
            metadata={"deal_name": "Project Pegasus", "passage": "Project Pegasus restructuring plan and debt recapitalization."}
        )
        self.store.ingest(req_b, embeddings=[[0.0, 1.0, 0.0]])

        # Query as Tenant A
        hits_a = self.store.dense_search("hedge_fund_alpha", [1.0, 0.0, 0.0], top_k=5)
        self.assertEqual(len(hits_a), 1)
        item_a = self.store.dense_item("hedge_fund_alpha", hits_a[0])
        self.assertEqual(item_a["tenant_id"], "hedge_fund_alpha")
        self.assertEqual(item_a["document_id"], "deal_doc_a")

        # Query as Tenant B with Tenant A's query vector
        hits_b = self.store.dense_search("hedge_fund_beta", [1.0, 0.0, 0.0], top_k=5)
        self.assertEqual(len(hits_b), 1)
        item_b = self.store.dense_item("hedge_fund_beta", hits_b[0])
        self.assertEqual(item_b["tenant_id"], "hedge_fund_beta")
        self.assertEqual(item_b["document_id"], "deal_doc_b")

        # Verify cross-tenant isolation: Tenant A has zero access to Tenant B index
        self.assertEqual(len(self.store._dense["hedge_fund_alpha"]), 1)
        self.assertEqual(len(self.store._dense["hedge_fund_beta"]), 1)

    def test_sec_edgar_atom_parser(self):
        """Tests parsing of SEC EDGAR Atom XML feed structure."""
        sample_atom_xml = """<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <title>Latest SEC Filings</title>
          <entry>
            <title>10-K - NVIDIA CORP (NVDA) (0001045810-24-000029)</title>
            <link href="https://www.sec.gov/Archives/edgar/data/1045810/000104581024000029/nvda-20240128.htm"/>
            <summary>Annual report for fiscal year ended January 28, 2024</summary>
          </entry>
        </feed>
        """
        filings = self.pipeline.parse_atom_feed(sample_atom_xml)
        self.assertEqual(len(filings), 1)
        self.assertEqual(filings[0]["ticker"], "NVDA")
        self.assertEqual(filings[0]["form_type"], "10-K")
        self.assertEqual(filings[0]["accession"], "0001045810-24-000029")

    def test_sec_pipeline_ingest_text(self):
        """Tests feeding parsed SEC text directly into the VectorStore."""
        sample_doc = (
            "Item 1A. Risk Factors\n\n"
            "Demand for accelerated computing solutions is influenced by enterprise AI adoption.\n\n"
            "Note 10. Leases\n\n"
            "Operating lease obligations total $850M through 2028."
        )
        count = self.pipeline.ingest_filing_text(
            document_text=sample_doc,
            ticker="NVDA",
            form_type="10-K",
            document_title="NVIDIA 10-K FY2024",
            source_url="https://sec.gov/sample"
        )
        self.assertGreaterEqual(count, 1)
        self.assertIn("public_markets", self.store._dense)


if __name__ == "__main__":
    unittest.main()

