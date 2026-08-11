"""Output validation for security guardrails.

Validates search response structure and detects leaked credentials in results.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from backend.schemas.retrieval import SearchResponse
from backend.security.config import get_security_config


@dataclass
class OutputViolation:
    """A single output validation violation."""

    violation_type: str  # structure, leaked_secret, format_error
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    message: str
    details: dict[str, Any] | None = None


@dataclass
class OutputValidationReport:
    """Report of output validation."""

    is_valid: bool
    violations: list[OutputViolation]
    validation_score: float  # 0.0 to 1.0, how confident we are in the output
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for logging."""
        return {
            "is_valid": self.is_valid,
            "violations": len(self.violations),
            "validation_score": round(self.validation_score, 2),
            "warnings": self.warnings,
            "violation_types": list(set(v.violation_type for v in self.violations)),
        }


class OutputValidator:
    """Validates search response structure and content safety."""

    # Patterns for leaked secrets/credentials in responses
    LEAKED_CREDENTIAL_PATTERNS = {
        "api_key": r"(api[_-]?key|apikey)['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{20,})['\"]?",
        "aws_key": r"(AKIA|ASIA)[0-9A-Z]{16}",
        "groq_key": r"gsk_[A-Za-z0-9]{20,}",
        "redis_url": r"redis(?:s)?://[^\s]+",
        "database_url": r"(postgres|mysql|mongodb)://[^\s]+",
        "bearer_token": r"Bearer\s+[A-Za-z0-9\-._~+/]+=*",
        "jwt_token": r"eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*",
        "aws_secret": r"aws_secret_access_key['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?",
    }

    def __init__(self) -> None:
        self.config = get_security_config()
        self._compiled_patterns: dict[str, re.Pattern] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile credential patterns."""
        for cred_type, pattern in self.LEAKED_CREDENTIAL_PATTERNS.items():
            try:
                self._compiled_patterns[cred_type] = re.compile(
                    pattern, re.IGNORECASE
                )
            except Exception:
                pass

    async def validate(self, response: SearchResponse) -> OutputValidationReport:
        """Validate a search response for structure and safety."""
        violations: list[OutputViolation] = []
        warnings: list[str] = []
        validation_score = 1.0

        # Step 1: Validate structure
        if not isinstance(response, SearchResponse):
            violations.append(
                OutputViolation(
                    violation_type="structure",
                    severity="CRITICAL",
                    message="Response is not a SearchResponse object",
                )
            )
            validation_score -= 0.5
            return OutputValidationReport(
                is_valid=False,
                violations=violations,
                validation_score=max(0.0, validation_score),
                warnings=warnings,
            )

        # Step 2: Validate required fields
        required_fields = ["tenant_id", "query", "hits"]
        for field in required_fields:
            if not hasattr(response, field):
                violations.append(
                    OutputViolation(
                        violation_type="structure",
                        severity="HIGH",
                        message=f"Missing required field: {field}",
                    )
                )
                validation_score -= 0.3

        # Step 3: Validate hits structure
        if response.hits:
            required_hit_fields = ["document_id", "passage", "score"]
            for i, hit in enumerate(response.hits):
                for field in required_hit_fields:
                    if not hasattr(hit, field):
                        violations.append(
                            OutputViolation(
                                violation_type="structure",
                                severity="MEDIUM",
                                message=f"Hit {i} missing field: {field}",
                                details={"hit_index": i},
                            )
                        )
                        validation_score -= 0.1

                # Validate score is a number
                if not isinstance(hit.score, (int, float)):
                    violations.append(
                        OutputViolation(
                            violation_type="format_error",
                            severity="MEDIUM",
                            message=f"Hit {i} score is not a number: {type(hit.score)}",
                            details={"hit_index": i},
                        )
                    )
                    validation_score -= 0.1

        # Step 4: Check for leaked credentials in passages
        if self.config.security_enabled:
            try:
                for i, hit in enumerate(response.hits or []):
                    passage_text = str(hit.passage)

                    for cred_type, pattern in self._compiled_patterns.items():
                        matches = pattern.findall(passage_text)
                        if matches:
                            violations.append(
                                OutputViolation(
                                    violation_type="leaked_secret",
                                    severity="CRITICAL",
                                    message=f"Potential leaked credential in hit {i}: {cred_type}",
                                    details={
                                        "hit_index": i,
                                        "credential_type": cred_type,
                                        "count": len(matches),
                                    },
                                )
                            )
                            validation_score -= 0.25
                            warnings.append(
                                f"Detected {len(matches)} potential {cred_type}(s) in response"
                            )

            except Exception as e:
                warnings.append(f"Credential detection failed: {str(e)}")

        # Step 5: Validate score ranges
        if response.hits:
            for i, hit in enumerate(response.hits):
                if isinstance(hit.score, (int, float)):
                    if not (0.0 <= hit.score <= 1.0):
                        violations.append(
                            OutputViolation(
                                violation_type="format_error",
                                severity="LOW",
                                message=f"Hit {i} score out of range [0, 1]: {hit.score}",
                                details={"hit_index": i, "score": hit.score},
                            )
                        )
                        validation_score -= 0.05

        # Determine if overall valid
        is_valid = len(
            [v for v in violations if v.severity in ("CRITICAL", "HIGH")]
        ) == 0

        return OutputValidationReport(
            is_valid=is_valid,
            violations=violations,
            validation_score=max(0.0, validation_score),
            warnings=warnings,
        )


def get_output_validator() -> OutputValidator | None:
    """Get the output validator (or None if security disabled)."""
    config = get_security_config()
    if config.security_enabled and config.output_validation_enabled:
        return OutputValidator()
    return None
