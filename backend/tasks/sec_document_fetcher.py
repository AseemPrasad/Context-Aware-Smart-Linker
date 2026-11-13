"""SEC EDGAR deep HTML/iXBRL document fetcher and section extractor.

Downloads primary 10-K, 10-Q, and 8-K documents from SEC archives, strips raw HTML/XBRL,
and isolates key regulatory sections (Item 1A, Item 7, Item 8) for vector chunking.
"""

from __future__ import annotations

import logging
import re
import urllib.request
from typing import Dict, Optional

logger = logging.getLogger(__name__)

SEC_HEADERS = {
    "User-Agent": "CASLResearchPlatform compliance@casl-research.com",
    "Accept-Encoding": "gzip, deflate",
    "Host": "www.sec.gov"
}


class SecDocumentFetcher:
    """Robust SEC document parser isolating critical disclosure sections."""

    @staticmethod
    def clean_html(html_text: str) -> str:
        """Removes script, style, XML/iXBRL tags while preserving readable paragraph flow."""
        # Remove script and style elements
        cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html_text, flags=re.DOTALL | re.IGNORECASE)
        # Remove HTML/XML tags
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        # Decode common HTML entities
        cleaned = cleaned.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&#160;", " ")
        # Condense whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    @classmethod
    def extract_key_sections(cls, full_text: str) -> Dict[str, str]:
        """Extracts high-impact items (Item 1A: Risk Factors, Item 7: MD&A)."""
        sections: Dict[str, str] = {}

        # Item 1A: Risk Factors
        item_1a_match = re.search(
            r"(?:item\s+1a[.:\s\-]+risk\s+factors)(.*?)(?:item\s+1b|item\s+2|$)",
            full_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if item_1a_match:
            sections["Item 1A - Risk Factors"] = item_1a_match.group(1).strip()[:15000]

        # Item 7: Management's Discussion and Analysis
        item_7_match = re.search(
            r"(?:item\s+7[.:\s\-]+management(?:'s)?\s+discussion)(.*?)(?:item\s+7a|item\s+8|$)",
            full_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if item_7_match:
            sections["Item 7 - MD&A"] = item_7_match.group(1).strip()[:15000]

        return sections

    @classmethod
    def fetch_filing_content(cls, filing_url: str, timeout: int = 15, max_bytes: int = 1_000_000) -> Optional[str]:
        """Fetches filing content via stream reader with strict bounded buffer to prevent OOM."""
        if not filing_url or not filing_url.startswith("http"):
            return None

        # Transform index URLs to raw document URLs if applicable
        raw_url = filing_url.replace("-index.htm", ".txt").replace("-index.html", ".txt")
        try:
            req = urllib.request.Request(raw_url, headers=SEC_HEADERS)
            chunks = []
            total_read = 0
            with urllib.request.urlopen(req, timeout=timeout) as response:
                while total_read < max_bytes:
                    chunk = response.read(65536)  # 64KB bounded chunks
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total_read += len(chunk)

            raw_bytes = b"".join(chunks)
            text = raw_bytes.decode("utf-8", errors="ignore")
            return cls.clean_html(text)
        except Exception as err:
            logger.debug("Failed to fetch full filing content from %s: %s", raw_url, err)
            return None
        except Exception as err:
            logger.debug("Failed to fetch full filing content from %s: %s", raw_url, err)
            return None

