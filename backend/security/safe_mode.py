"""Safe-mode recovery handler for security layer failures.

Ensures system never breaks due to security layer issues.
Provides graceful degradation when security processing fails.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from backend.security.config import get_security_config


class SafeModeReason(str, Enum):
    """Reasons for safe-mode activation."""

    PII_MASKING_FAILED = "pii_masking_failed"
    INJECTION_DETECTION_FAILED = "injection_detection_failed"
    OUTPUT_VALIDATION_FAILED = "output_validation_failed"
    ENCODING_ERROR = "encoding_error"
    REGEX_TIMEOUT = "regex_timeout"
    UNKNOWN_ERROR = "unknown_error"


class SafeModeHandler:
    """Handles graceful degradation when security layer fails."""

    def __init__(self) -> None:
        self.config = get_security_config()
        self._safe_mode_activations: list[tuple[SafeModeReason, str]] = []

    def should_allow_bypass(self) -> bool:
        """Check if safe-mode should allow bypass on security failures."""
        return self.config.safe_mode_enabled

    def handle_pii_masking_failure(self, error: Exception) -> str:
        """Handle PII masking failure with safe-mode bypass.

        Returns the original text if safe-mode enabled, otherwise raises.
        """
        reason = SafeModeReason.PII_MASKING_FAILED
        message = f"PII masking failed: {str(error)}"

        if self.should_allow_bypass():
            self._record_activation(reason, message)
            return None  # Return None to signal bypass
        else:
            raise ValueError(f"Security failure in safe-mode disabled: {message}")

    def handle_injection_detection_failure(self, error: Exception) -> bool:
        """Handle injection detection failure with safe-mode bypass.

        Returns False (no injection) if safe-mode enabled, otherwise raises.
        """
        reason = SafeModeReason.INJECTION_DETECTION_FAILED
        message = f"Injection detection failed: {str(error)}"

        if self.should_allow_bypass():
            self._record_activation(reason, message)
            return False  # Assume no injection in safe-mode
        else:
            raise ValueError(f"Security failure in safe-mode disabled: {message}")

    def handle_output_validation_failure(self, error: Exception) -> dict[str, Any]:
        """Handle output validation failure with safe-mode bypass.

        Returns a clean validation report if safe-mode enabled, otherwise raises.
        """
        reason = SafeModeReason.OUTPUT_VALIDATION_FAILED
        message = f"Output validation failed: {str(error)}"

        if self.should_allow_bypass():
            self._record_activation(reason, message)
            return {
                "is_valid": True,
                "violations": [],
                "validation_score": 0.5,  # Degraded score in safe-mode
                "warnings": [f"Validation skipped: {message}"],
            }
        else:
            raise ValueError(f"Security failure in safe-mode disabled: {message}")

    def handle_regex_timeout(self, operation: str) -> None:
        """Handle regex timeout in security operations."""
        reason = SafeModeReason.REGEX_TIMEOUT
        message = f"Regex timeout in {operation}"

        if self.should_allow_bypass():
            self._record_activation(reason, message)
        else:
            raise TimeoutError(f"Security operation timeout: {message}")

    def handle_encoding_error(self, error: Exception) -> None:
        """Handle encoding errors in input validation."""
        reason = SafeModeReason.ENCODING_ERROR
        message = f"Encoding error: {str(error)}"

        if self.should_allow_bypass():
            self._record_activation(reason, message)
        else:
            raise UnicodeError(f"Security failure in safe-mode disabled: {message}")

    def _record_activation(self, reason: SafeModeReason, message: str) -> None:
        """Record a safe-mode activation for audit trail."""
        self._safe_mode_activations.append((reason, message))
        # Keep only last 100 activations
        if len(self._safe_mode_activations) > 100:
            self._safe_mode_activations = self._safe_mode_activations[-100:]

    def get_activations(self) -> list[tuple[SafeModeReason, str]]:
        """Get all recorded safe-mode activations."""
        return self._safe_mode_activations.copy()

    def get_recent_activations(self, count: int = 10) -> list[tuple[SafeModeReason, str]]:
        """Get most recent safe-mode activations."""
        return self._safe_mode_activations[-count:]

    def clear_activations(self) -> None:
        """Clear activation history (useful for testing)."""
        self._safe_mode_activations = []


_safe_mode_handler: SafeModeHandler | None = None


def get_safe_mode_handler() -> SafeModeHandler:
    """Get the safe-mode handler singleton."""
    global _safe_mode_handler
    if _safe_mode_handler is None:
        _safe_mode_handler = SafeModeHandler()
    return _safe_mode_handler
