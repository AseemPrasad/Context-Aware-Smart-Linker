"""Autonomous SEC EDGAR filing ingestion pipeline.

Fetches the latest public 10-K, 10-Q, and 8-K filings from the SEC EDGAR RSS/Atom feed,
extracts and chunks content using FinancialDocumentParser, and indexes into the VectorStore
under the 'public_markets' tenant.
"""

from __future__ import annotations

import logging
import re
import os
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from backend.core.encoder import get_encoder
from backend.db.vector_store import VectorStore
from backend.domains.finance.parser import FinancialDocumentParser
from backend.schemas.retrieval import IngestRequest

logger = logging.getLogger(__name__)

SEC_FEED_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=10-K,10-Q,8-K&output=atom"
# SEC EDGAR requires compliant User-Agent format: SampleCompany AdminContact@<domain>.com
SEC_USER_AGENT = os.getenv("SEC_EDGAR_USER_AGENT", "CASLResearchPlatform compliance@casl-research.com")


class SecEdgarPipeline:
    """Poller and ingester for live SEC EDGAR disclosures."""

    def __init__(self, store: Optional[VectorStore] = None):
        self.store = store or VectorStore()
        self.parser = FinancialDocumentParser()
        self.seen_accessions: set[str] = set()

    def parse_atom_feed(self, xml_content: str) -> List[Dict[str, str]]:
        """Parses SEC Atom XML feed into structured filing metadata entries."""
        filings: List[Dict[str, str]] = []
        try:
            root = ET.fromstring(xml_content)
            namespace = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", namespace):
                title_elem = entry.find("atom:title", namespace)
                link_elem = entry.find("atom:link", namespace)
                summary_elem = entry.find("atom:summary", namespace)

                title = title_elem.text if title_elem is not None else ""
                link = link_elem.get("href", "") if link_elem is not None else ""
                summary = summary_elem.text if summary_elem is not None else ""

                # Extract accession number and ticker if available
                accession_match = re.search(r"\b\d{10}-\d{2}-\d{6}\b", f"{title} {link} {summary}")
                accession = accession_match.group(0) if accession_match else link

                ticker_match = re.search(r"\(([A-Z]{1,5})\)", title)
                ticker = ticker_match.group(1) if ticker_match else "SEC"

                form_match = re.search(r"\b(10-K|10-Q|8-K|S-1)\b", title, re.IGNORECASE)
                form_type = form_match.group(0).upper() if form_match else "FILING"

                filings.append({
                    "accession": accession,
                    "title": title,
                    "link": link,
                    "ticker": ticker,
                    "form_type": form_type,
                    "summary": summary
                })
        except Exception as e:
            logger.warning("Failed to parse SEC Atom feed: %s", e)
        return filings

    def ingest_filing_text(
        self,
        document_text: str,
        ticker: str,
        form_type: str,
        document_title: str,
        source_url: str,
        tenant_id: str = "public_markets"
    ) -> int:
        """Chunks and stores filing text into VectorStore with full provenance."""
        chunks = self.parser.chunk_filing(
            text=document_text,
            ticker=ticker,
            form_type=form_type,
            document_title=document_title
        )

        encoder = get_encoder()
        texts = [chunk["content"] for chunk in chunks]
        embeddings = encoder.encode(texts)

        for i, chunk in enumerate(chunks):
            doc_id = f"{ticker}_{form_type}_{i}"
            meta = chunk["metadata"]
            meta["source_url"] = source_url
            meta["passage"] = chunk["content"]

            request = IngestRequest(
                document_id=doc_id,
                text=chunk["content"],
                tenant_id=tenant_id,
                metadata=meta
            )
            emb = [embeddings[i]] if i < len(embeddings) else [[0.0] * 384]
            self.store.ingest(request, embeddings=emb)

        return len(chunks)


# Celery task hook (invocable via Celery worker or async loop)
def sync_latest_sec_filings_task(mock_feed: Optional[str] = None) -> Dict[str, Any]:
    """Sync task for Celery beat or manual ingestion trigger with deep filing ingestion."""
    pipeline = SecEdgarPipeline()
    if mock_feed:
        filings = pipeline.parse_atom_feed(mock_feed)
    else:
        try:
            req = urllib.request.Request(SEC_FEED_URL, headers={"User-Agent": SEC_USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode("utf-8", errors="ignore")
            filings = pipeline.parse_atom_feed(content)
        except Exception as err:
            logger.warning("Network fetch for SEC feed failed: %s", err)
            return {"status": "skipped", "reason": str(err), "ingested_count": 0}

    total_chunks = 0
    for filing in filings[:5]:  # Batch top 5 filings to respect SEC rate limit (10 req/s)
        accession = filing.get("accession")
        if not accession or accession in pipeline.seen_accessions:
            continue
        pipeline.seen_accessions.add(accession)
        
        # Ingest filing summary or body
        body_text = filing.get("summary") or filing.get("title") or ""
        if body_text.strip():
            chunks = pipeline.ingest_filing_text(
                document_text=body_text,
                ticker=filing.get("ticker", "SEC"),
                form_type=filing.get("form_type", "FILING"),
                document_title=filing.get("title", ""),
                source_url=filing.get("link", ""),
                tenant_id="public_markets"
            )
            total_chunks += chunks

    return {"status": "success", "filings_discovered": len(filings), "ingested_chunks": total_chunks}

