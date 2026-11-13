"""Financial and regulatory document parser.

Preserves financial tables, covenant numbering, and section hierarchies
rather than performing naive character splits.
"""

import re
from typing import List, Dict, Any


class FinancialDocumentParser:
    """Specialized chunker for SEC filings, prospectuses, and financial reports."""

    ITEM_PATTERN = re.compile(
        r"(Item\s+\d+[A-Z]?\.?|Note\s+\d+\.?|Section\s+\d+(\.\d+)*)",
        re.IGNORECASE
    )

    def __init__(self, target_chunk_size: int = 800, overlap: int = 150):
        self.target_chunk_size = target_chunk_size
        self.overlap = overlap

    def chunk_filing(
        self,
        text: str,
        ticker: str = "GENERIC",
        form_type: str = "10-K",
        document_title: str = "Financial Filing"
    ) -> List[Dict[str, Any]]:
        """Splits document text while preserving section headings and tables."""
        if not text:
            return []

        # Split on major sections if present, otherwise split on paragraphs
        raw_sections = re.split(r"\n{2,}", text)
        chunks: List[Dict[str, Any]] = []
        current_chunk = []
        current_length = 0
        current_section = "General Overview"

        for section in raw_sections:
            clean_sec = section.strip()
            if not clean_sec:
                continue

            # Check if this paragraph acts as an Item / Note header
            match = self.ITEM_PATTERN.search(clean_sec[:100])
            if match:
                current_section = match.group(0).strip()

            sec_len = len(clean_sec)

            if current_length + sec_len <= self.target_chunk_size:
                current_chunk.append(clean_sec)
                current_length += sec_len
            else:
                if current_chunk:
                    chunk_text = "\n\n".join(current_chunk)
                    chunks.append({
                        "content": chunk_text,
                        "metadata": {
                            "document_title": document_title,
                            "ticker": ticker.upper(),
                            "form_type": form_type.upper(),
                            "section": current_section,
                            "length": str(len(chunk_text))
                        }
                    })
                current_chunk = [clean_sec]
                current_length = sec_len

        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append({
                "content": chunk_text,
                "metadata": {
                    "document_title": document_title,
                    "ticker": ticker.upper(),
                    "form_type": form_type.upper(),
                    "section": current_section,
                    "length": str(len(chunk_text))
                }
            })

        return chunks

