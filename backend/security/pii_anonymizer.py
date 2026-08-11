"""PII detection and anonymization for enterprise guardrails.

Detects and masks personally identifiable information using regex patterns.
Handles: emails, phone numbers, SSNs, API keys, IP addresses, credentials.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from backend.security.config import get_security_config


@dataclass
class PiiRedaction:
    """Records a single PII redaction."""

    pii_type: str  # email, phone, ssn, api_key, ip_address, credential
    original: str
    redacted_as: str
    position: tuple[int, int]  # (start, end) in original text


@dataclass
class PiiRedactionReport:
    """Report of all PII redactions performed."""

    original_text: str
    masked_text: str
    redactions: list[PiiRedaction] = field(default_factory=list)
    total_pii_found: int = 0

    def by_type(self, pii_type: str) -> list[PiiRedaction]:
        """Get redactions of a specific type."""
        return [r for r in self.redactions if r.pii_type == pii_type]

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for logging."""
        return {
            "total_pii_found": self.total_pii_found,
            "by_type": {
                "emails": len(self.by_type("email")),
                "phones": len(self.by_type("phone")),
                "ssns": len(self.by_type("ssn")),
                "api_keys": len(self.by_type("api_key")),
                "ip_addresses": len(self.by_type("ip_address")),
                "credentials": len(self.by_type("credential")),
            },
        }


class PiiAnonymizer:
    """Detects and redacts PII in text."""

    # Patterns for different PII types
    PATTERNS = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"(\+?1?[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "api_key_aws": r"(AKIA|ASIA)[0-9A-Z]{16}",
        "api_key_groq": r"gsk_[A-Za-z0-9]{20,}",
        "api_key_generic": r"(api[_-]?key|apikey)['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{20,})['\"]?",
        "ip_address_v4": r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
        "ip_address_v6": r"(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4})",
        "credential": r"(password|passwd|pwd|secret|token|auth|credential)['\"]?\s*[:=]\s*['\"]?([^\s'\"\n]{6,})['\"]?",
    }

    MASK_STRINGS = {
        "email": "[EMAIL_REDACTED]",
        "phone": "[PHONE_REDACTED]",
        "ssn": "[SSN_REDACTED]",
        "api_key": "[API_KEY_REDACTED]",
        "ip_address": "[IP_REDACTED]",
        "credential": "[CREDENTIAL_REDACTED]",
    }

    def __init__(self) -> None:
        self.config = get_security_config()
        self._compiled_patterns: dict[str, re.Pattern] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        for pii_type, pattern in self.PATTERNS.items():
            try:
                self._compiled_patterns[pii_type] = re.compile(pattern, re.IGNORECASE)
            except Exception:
                pass  # Skip invalid patterns

    def anonymize(self, text: str) -> PiiRedactionReport:
        """Scan text for PII and return redacted version with report."""
        if not text:
            return PiiRedactionReport(original_text="", masked_text="", redactions=[])

        masked_text = text
        redactions: list[PiiRedaction] = []
        offset = 0  # Track position changes as we replace

        # Scan for emails
        if self.config.pii_mask_emails:
            masked_text, email_redactions = self._redact_pattern(
                masked_text, "email", offset
            )
            redactions.extend(email_redactions)
            offset += sum(
                len(r.redacted_as) - len(r.original) for r in email_redactions
            )

        # Scan for phone numbers
        if self.config.pii_mask_phones:
            masked_text, phone_redactions = self._redact_pattern(
                masked_text, "phone", offset
            )
            redactions.extend(phone_redactions)
            offset += sum(
                len(r.redacted_as) - len(r.original) for r in phone_redactions
            )

        # Scan for SSNs
        if self.config.pii_mask_ssns:
            masked_text, ssn_redactions = self._redact_pattern(
                masked_text, "ssn", offset
            )
            redactions.extend(ssn_redactions)
            offset += sum(
                len(r.redacted_as) - len(r.original) for r in ssn_redactions
            )

        # Scan for API keys
        if self.config.pii_mask_api_keys:
            for key_type in ["api_key_aws", "api_key_groq", "api_key_generic"]:
                masked_text, key_redactions = self._redact_pattern(
                    masked_text, key_type, offset
                )
                redactions.extend(key_redactions)
                offset += sum(
                    len(r.redacted_as) - len(r.original) for r in key_redactions
                )

        # Scan for IP addresses
        if self.config.pii_mask_ips:
            for ip_type in ["ip_address_v4", "ip_address_v6"]:
                masked_text, ip_redactions = self._redact_pattern(
                    masked_text, ip_type, offset
                )
                redactions.extend(ip_redactions)
                offset += sum(
                    len(r.redacted_as) - len(r.original) for r in ip_redactions
                )

        # Scan for credentials (generic password/token patterns)
        if self.config.pii_mask_api_keys:
            masked_text, cred_redactions = self._redact_pattern(
                masked_text, "credential", offset
            )
            redactions.extend(cred_redactions)

        return PiiRedactionReport(
            original_text=text,
            masked_text=masked_text,
            redactions=redactions,
            total_pii_found=len(redactions),
        )

    def _redact_pattern(
        self, text: str, pii_type: str, offset: int = 0
    ) -> tuple[str, list[PiiRedaction]]:
        """Find and redact a specific PII pattern."""
        pattern = self._compiled_patterns.get(pii_type)
        if not pattern:
            return text, []

        redactions: list[PiiRedaction] = []
        result = text

        try:
            matches = list(pattern.finditer(text))
            # Process matches in reverse order to maintain positions
            for match in reversed(matches):
                original = match.group(0)
                # Determine mask string based on pattern type
                if pii_type.startswith("api_key") or pii_type == "credential":
                    mask = self.MASK_STRINGS["api_key"]
                elif pii_type.startswith("ip_address"):
                    mask = self.MASK_STRINGS["ip_address"]
                else:
                    mask = self.MASK_STRINGS.get(pii_type, "[REDACTED]")

                start_pos = match.start()
                end_pos = match.end()

                redactions.insert(
                    0,
                    PiiRedaction(
                        pii_type=pii_type,
                        original=original,
                        redacted_as=mask,
                        position=(start_pos, end_pos),
                    ),
                )
                result = result[:start_pos] + mask + result[end_pos:]

        except Exception:
            # Fail silent: if regex fails, return unmasked
            pass

        return result, redactions


def get_pii_anonymizer() -> PiiAnonymizer:
    """Get the PII anonymizer instance."""
    return PiiAnonymizer()
