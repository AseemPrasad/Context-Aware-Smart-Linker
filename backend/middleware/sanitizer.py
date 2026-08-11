"""Input sanitization middleware for security guardrails.

Chains PII anonymization + prompt injection detection.
Validates input size and encoding before forwarding to retrieval engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.schemas.retrieval import SearchRequest
from backend.security.config import get_security_config
from backend.security.injection_detector import (
    InjectionDetectionReport,
    get_injection_detector,
)
from backend.security.pii_anonymizer import PiiRedactionReport, get_pii_anonymizer


@dataclass
class SanitizationReport:
    """Report of input sanitization."""

    is_safe: bool
    pii_report: PiiRedactionReport | None
    injection_report: InjectionDetectionReport | None
    blocked_reason: str | None = None
    warnings: list[str] = None

    def __post_init__(self) -> None:
        if self.warnings is None:
            self.warnings = []

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for logging."""
        return {
            "is_safe": self.is_safe,
            "blocked": self.blocked_reason is not None,
            "blocked_reason": self.blocked_reason,
            "warnings": self.warnings,
            "pii_redacted": self.pii_report.total_pii_found if self.pii_report else 0,
            "injections_detected": self.injection_report.total_matches if self.injection_report else 0,
        }


class InputSanitizer:
    """Sanitizes search requests by removing PII and detecting injections."""

    def __init__(self) -> None:
        self.config = get_security_config()
        self.pii_anonymizer = get_pii_anonymizer()
        self.injection_detector = get_injection_detector()

    async def sanitize(
        self, request: SearchRequest
    ) -> tuple[SearchRequest, SanitizationReport]:
        """Sanitize a search request and return sanitized version + report.

        Applies:
        1. Input size validation
        2. Encoding validation
        3. PII anonymization (if enabled)
        4. Injection detection (if enabled)

        Returns sanitized request + report. If safe_mode enabled,
        always returns original request on failures.
        """
        warnings: list[str] = []

        # Step 1: Size validation
        context_size = len(request.query) + len(request.query)
        if context_size > self.config.max_context_size:
            warnings.append(
                f"Context size {context_size} exceeds limit {self.config.max_context_size}"
            )
            if not self.config.safe_mode_enabled:
                return (
                    request,
                    SanitizationReport(
                        is_safe=False,
                        pii_report=None,
                        injection_report=None,
                        blocked_reason="Input size exceeds maximum allowed",
                        warnings=warnings,
                    ),
                )

        # Step 2: Encoding validation
        try:
            request.query.encode("utf-8")
        except UnicodeEncodeError as e:
            warnings.append(f"Invalid UTF-8 encoding: {str(e)}")
            if not self.config.safe_mode_enabled:
                return (
                    request,
                    SanitizationReport(
                        is_safe=False,
                        pii_report=None,
                        injection_report=None,
                        blocked_reason="Invalid character encoding",
                        warnings=warnings,
                    ),
                )

        # Step 3: PII Anonymization
        pii_report = None
        sanitized_query = request.query

        if self.config.security_enabled and self.config.pii_masking_enabled:
            try:
                pii_report = self.pii_anonymizer.anonymize(request.query)
                sanitized_query = pii_report.masked_text

                if pii_report.total_pii_found > 0:
                    warnings.append(
                        f"Redacted {pii_report.total_pii_found} PII instances"
                    )
            except Exception as e:
                warnings.append(f"PII masking failed: {str(e)}")
                if not self.config.safe_mode_enabled:
                    return (
                        request,
                        SanitizationReport(
                            is_safe=False,
                            pii_report=None,
                            injection_report=None,
                            blocked_reason="PII masking failed",
                            warnings=warnings,
                        ),
                    )

        # Step 4: Injection Detection
        injection_report = None
        is_injection = False

        if self.config.security_enabled and self.config.injection_detection_enabled:
            try:
                injection_report = self.injection_detector.detect(sanitized_query)
                is_injection = injection_report.is_injection_detected

                if is_injection:
                    warnings.append(
                        f"Detected {injection_report.total_matches} injection patterns"
                    )

                    # Check if severity is blocked
                    if self.config.is_injection_severity_blocked(
                        injection_report.highest_severity
                    ):
                        if not self.config.safe_mode_enabled:
                            return (
                                request,
                                SanitizationReport(
                                    is_safe=False,
                                    pii_report=pii_report,
                                    injection_report=injection_report,
                                    blocked_reason=f"Prompt injection detected (severity: {injection_report.highest_severity})",
                                    warnings=warnings,
                                ),
                            )

            except Exception as e:
                warnings.append(f"Injection detection failed: {str(e)}")
                if not self.config.safe_mode_enabled:
                    return (
                        request,
                        SanitizationReport(
                            is_safe=False,
                            pii_report=pii_report,
                            injection_report=None,
                            blocked_reason="Injection detection failed",
                            warnings=warnings,
                        ),
                    )

        # Build sanitized request
        sanitized_request = SearchRequest(
            tenant_id=request.tenant_id,
            query=sanitized_query,
            top_k=request.top_k,
            use_rerank=request.use_rerank,
        )

        # Determine if overall safe
        is_safe = not (
            is_injection
            and self.config.is_injection_severity_blocked(
                injection_report.highest_severity if injection_report else "LOW"
            )
        )

        return (
            sanitized_request,
            SanitizationReport(
                is_safe=is_safe,
                pii_report=pii_report,
                injection_report=injection_report,
                blocked_reason=None if is_safe else "Security check failed",
                warnings=warnings,
            ),
        )


def get_input_sanitizer() -> InputSanitizer | None:
    """Get the input sanitizer (or None if security disabled)."""
    config = get_security_config()
    if config.security_enabled:
        return InputSanitizer()
    return None
