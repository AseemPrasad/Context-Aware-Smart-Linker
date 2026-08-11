"""Security metrics and health monitoring for guardrails.

Tracks PII redactions, injections detected, and output violations.
Provides observability into security layer health and performance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backend.security.injection_detector import InjectionDetectionReport
from backend.security.pii_anonymizer import PiiRedactionReport
from backend.observability.tracer import get_tracer


@dataclass
class SecurityStats:
    """Aggregated security statistics."""

    # PII redactions
    total_pii_redacted: int = 0
    emails_redacted: int = 0
    phones_redacted: int = 0
    api_keys_redacted: int = 0
    ip_addresses_redacted: int = 0
    ssns_redacted: int = 0

    # Injections detected
    total_injections_detected: int = 0
    override_patterns_detected: int = 0
    escape_patterns_detected: int = 0
    jailbreak_patterns_detected: int = 0

    # Output violations
    total_violations_detected: int = 0
    structure_violations: int = 0
    format_violations: int = 0
    leaked_secrets_detected: int = 0

    # Blocking events
    total_requests_blocked: int = 0
    blocked_by_injection: int = 0
    blocked_by_size: int = 0

    # Last events
    last_pii_redaction_time: datetime | None = None
    last_injection_detection_time: datetime | None = None
    last_violation_time: datetime | None = None
    last_block_time: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary for API responses."""
        return {
            "pii_redacted": {
                "total": self.total_pii_redacted,
                "emails": self.emails_redacted,
                "phones": self.phones_redacted,
                "api_keys": self.api_keys_redacted,
                "ip_addresses": self.ip_addresses_redacted,
                "ssns": self.ssns_redacted,
            },
            "injections_detected": {
                "total": self.total_injections_detected,
                "override_patterns": self.override_patterns_detected,
                "escape_patterns": self.escape_patterns_detected,
                "jailbreak_patterns": self.jailbreak_patterns_detected,
            },
            "output_violations": {
                "total": self.total_violations_detected,
                "structure_violations": self.structure_violations,
                "format_violations": self.format_violations,
                "leaked_secrets": self.leaked_secrets_detected,
            },
            "blocking_events": {
                "total_requests_blocked": self.total_requests_blocked,
                "blocked_by_injection": self.blocked_by_injection,
                "blocked_by_size": self.blocked_by_size,
            },
            "last_events": {
                "last_pii_redaction": self.last_pii_redaction_time.isoformat() if self.last_pii_redaction_time else None,
                "last_injection_detection": self.last_injection_detection_time.isoformat() if self.last_injection_detection_time else None,
                "last_violation": self.last_violation_time.isoformat() if self.last_violation_time else None,
                "last_block": self.last_block_time.isoformat() if self.last_block_time else None,
            },
        }


class SecurityMonitor:
    """Singleton monitor for security metrics."""

    _instance: SecurityMonitor | None = None
    _stats: SecurityStats = field(default_factory=SecurityStats)

    def __new__(cls) -> SecurityMonitor:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._stats = SecurityStats()
        return cls._instance

    def record_pii_redaction(self, report: PiiRedactionReport) -> None:
        """Record PII redaction results."""
        if not report or report.total_pii_found == 0:
            return

        tracer = get_tracer()
        tracer.start_as_current_span("security.pii_redaction").__enter__()

        self._stats.total_pii_redacted += report.total_pii_found
        self._stats.last_pii_redaction_time = datetime.utcnow()

        for redaction in report.redactions:
            if redaction.pii_type == "email":
                self._stats.emails_redacted += 1
            elif redaction.pii_type == "phone":
                self._stats.phones_redacted += 1
            elif redaction.pii_type.startswith("api_key"):
                self._stats.api_keys_redacted += 1
            elif redaction.pii_type.startswith("ip_address"):
                self._stats.ip_addresses_redacted += 1
            elif redaction.pii_type == "ssn":
                self._stats.ssns_redacted += 1

        with tracer.start_as_current_span("security.pii_detected") as span:
            span.set_attribute("total_pii_found", report.total_pii_found)
            span.set_attribute("emails", self._stats.emails_redacted)
            span.set_attribute("phones", self._stats.phones_redacted)
            span.set_attribute("api_keys", self._stats.api_keys_redacted)

    def record_injection_detection(self, report: InjectionDetectionReport) -> None:
        """Record injection detection results."""
        if not report or report.total_matches == 0:
            return

        tracer = get_tracer()

        with tracer.start_as_current_span("security.injection_detected") as span:
            self._stats.total_injections_detected += report.total_matches
            self._stats.last_injection_detection_time = datetime.utcnow()

            for pattern in report.patterns_found:
                if pattern.pattern_type == "override":
                    self._stats.override_patterns_detected += 1
                elif pattern.pattern_type == "escape":
                    self._stats.escape_patterns_detected += 1
                elif pattern.pattern_type == "jailbreak":
                    self._stats.jailbreak_patterns_detected += 1

            span.set_attribute("total_injections", report.total_matches)
            span.set_attribute("override_patterns", self._stats.override_patterns_detected)
            span.set_attribute("escape_patterns", self._stats.escape_patterns_detected)
            span.set_attribute("jailbreak_patterns", self._stats.jailbreak_patterns_detected)

    def record_injection_block(self) -> None:
        """Record when a request is blocked due to injection."""
        tracer = get_tracer()

        with tracer.start_as_current_span("security.injection_blocked") as span:
            self._stats.total_requests_blocked += 1
            self._stats.blocked_by_injection += 1
            self._stats.last_block_time = datetime.utcnow()
            span.set_attribute("total_blocked", self._stats.total_requests_blocked)

    def record_size_block(self) -> None:
        """Record when a request is blocked due to size."""
        tracer = get_tracer()

        with tracer.start_as_current_span("security.size_blocked") as span:
            self._stats.total_requests_blocked += 1
            self._stats.blocked_by_size += 1
            self._stats.last_block_time = datetime.utcnow()
            span.set_attribute("total_blocked", self._stats.total_requests_blocked)

    def record_output_violation(self, violation_type: str) -> None:
        """Record an output validation violation."""
        tracer = get_tracer()

        with tracer.start_as_current_span("security.output_violation") as span:
            self._stats.total_violations_detected += 1
            self._stats.last_violation_time = datetime.utcnow()

            if violation_type == "structure":
                self._stats.structure_violations += 1
            elif violation_type == "format_error":
                self._stats.format_violations += 1
            elif violation_type == "leaked_secret":
                self._stats.leaked_secrets_detected += 1

            span.set_attribute("violation_type", violation_type)
            span.set_attribute("total_violations", self._stats.total_violations_detected)

    def get_stats(self) -> SecurityStats:
        """Get current security statistics."""
        return self._stats

    def reset_stats(self) -> None:
        """Reset all statistics (useful for testing)."""
        self._stats = SecurityStats()


def get_security_monitor() -> SecurityMonitor:
    """Get the security monitor singleton."""
    return SecurityMonitor()
