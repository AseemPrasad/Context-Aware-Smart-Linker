"""Security configuration for enterprise guardrails.

Centralizes all security-related settings with sensible defaults.
All settings can be overridden via environment variables.
Security is disabled by default to avoid impact on existing deployments.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class SecurityConfig:
    """Configuration for enterprise guardrails engine."""

    # Master feature flags
    security_enabled: bool = os.getenv("SECURITY_ENABLED", "false").lower() == "true"
    pii_masking_enabled: bool = os.getenv("PII_MASKING_ENABLED", "true").lower() == "true"
    injection_detection_enabled: bool = os.getenv("INJECTION_DETECTION_ENABLED", "true").lower() == "true"
    output_validation_enabled: bool = os.getenv("OUTPUT_VALIDATION_ENABLED", "true").lower() == "true"

    # Safe-mode: allow requests through if security layer fails
    safe_mode_enabled: bool = os.getenv("SECURITY_SAFE_MODE", "true").lower() == "true"

    # Input validation thresholds
    max_context_size: int = int(os.getenv("MAX_CONTEXT_SIZE", "50000"))  # bytes
    max_context_lines: int = int(os.getenv("MAX_CONTEXT_LINES", "1000"))  # lines

    # Injection detection thresholds
    injection_severity_threshold: str = os.getenv("INJECTION_SEVERITY_THRESHOLD", "HIGH")  # CRITICAL, HIGH, MEDIUM, LOW
    injection_confidence_threshold: float = float(os.getenv("INJECTION_CONFIDENCE_THRESHOLD", "0.7"))

    # PII masking configuration
    pii_mask_emails: bool = os.getenv("PII_MASK_EMAILS", "true").lower() == "true"
    pii_mask_phones: bool = os.getenv("PII_MASK_PHONES", "true").lower() == "true"
    pii_mask_api_keys: bool = os.getenv("PII_MASK_API_KEYS", "true").lower() == "true"
    pii_mask_ips: bool = os.getenv("PII_MASK_IPS", "true").lower() == "true"
    pii_mask_ssns: bool = os.getenv("PII_MASK_SSNS", "true").lower() == "true"

    # Custom blocklist patterns (comma-separated regex)
    custom_injection_patterns: str = os.getenv("CUSTOM_INJECTION_PATTERNS", "")

    # Performance settings
    regex_timeout_seconds: float = float(os.getenv("REGEX_TIMEOUT_SECONDS", "2.0"))
    max_patterns_to_scan: int = int(os.getenv("MAX_PATTERNS_TO_SCAN", "100"))

    # Logging & monitoring
    log_all_sanitization: bool = os.getenv("LOG_ALL_SANITIZATION", "false").lower() == "true"
    log_all_violations: bool = os.getenv("LOG_ALL_VIOLATIONS", "true").lower() == "true"

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.max_context_size <= 0:
            raise ValueError(f"max_context_size must be positive, got {self.max_context_size}")

        if self.injection_severity_threshold not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            raise ValueError(f"injection_severity_threshold must be one of CRITICAL/HIGH/MEDIUM/LOW, got {self.injection_severity_threshold}")

        if not 0.0 <= self.injection_confidence_threshold <= 1.0:
            raise ValueError(f"injection_confidence_threshold must be in [0.0, 1.0], got {self.injection_confidence_threshold}")

        if self.regex_timeout_seconds <= 0:
            raise ValueError(f"regex_timeout_seconds must be positive, got {self.regex_timeout_seconds}")

    def is_injection_severity_blocked(self, severity: str) -> bool:
        """Check if injection severity should block the request."""
        severity_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        threshold_rank = severity_rank.get(self.injection_severity_threshold, 3)
        return severity_rank.get(severity, 0) >= threshold_rank


def get_security_config() -> SecurityConfig:
    """Get the security configuration singleton."""
    return SecurityConfig()
