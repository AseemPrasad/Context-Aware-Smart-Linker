"""Tests for Financial and Regulatory Due Diligence domain."""

import unittest
from backend.domains.finance.parser import FinancialDocumentParser
from backend.domains.finance.schemas import (
    FinancialAnalysisRequest,
    FinancialAnalysisResponse,
    FinancialCitation,
)


class TestFinancialParser(unittest.TestCase):
    def setUp(self):
        self.parser = FinancialDocumentParser(target_chunk_size=300, overlap=50)

    def test_chunk_filing_preserves_sections(self):
        doc = (
            "Item 1A. Risk Factors\n\n"
            "Our semiconductor revenue is highly dependent on global supply chains and geopolitical stability. "
            "Export controls may impact sales to international cloud customers.\n\n"
            "Note 14. Long-Term Debt\n\n"
            "The Company has $1.25B outstanding in senior unsecured notes due 2030."
        )
        chunks = self.parser.chunk_filing(doc, ticker="TEST", form_type="10-K", document_title="Test 10-K")
        self.assertGreaterEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["metadata"]["ticker"], "TEST")
        self.assertEqual(chunks[0]["metadata"]["form_type"], "10-K")

    def test_empty_document(self):
        chunks = self.parser.chunk_filing("")
        self.assertEqual(chunks, [])


class TestFinancialSchemas(unittest.TestCase):
    def test_request_and_response_validation(self):
        req = FinancialAnalysisRequest(
            term="Debt Covenant",
            surrounding_context="Under the 2024 credit facility, debt covenants require leverage ratio < 3.5x.",
            page_title="Acme Corp S-1 Prospectus",
            ticker="ACME"
        )
        self.assertEqual(req.ticker, "ACME")

        citation = FinancialCitation(
            source_id="chunk_982",
            document_title="Acme S-1",
            ticker="ACME",
            form_type="S-1",
            section="Section 4.02",
            excerpt="Leverage ratio must not exceed 3.50:1.00 at each fiscal quarter end.",
            source_url="https://sec.gov/edgar/data/12345/s1.htm"
        )

        resp = FinancialAnalysisResponse(
            term=req.term,
            executive_summary="Debt covenant specifies minimum solvency and debt-to-equity compliance limits.",
            citations=[citation],
            confidence_score=0.98,
            cached=False
        )

        self.assertEqual(len(resp.citations), 1)
        self.assertEqual(resp.citations[0].section, "Section 4.02")
        self.assertEqual(resp.confidence_score, 0.98)


if __name__ == "__main__":
    unittest.main()

