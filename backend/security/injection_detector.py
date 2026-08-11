"""Prompt injection attack detection for enterprise guardrails.

Scans input context for known attack patterns and prompt override attempts.
Detects: override patterns, escape attempts, jailbreak/roleplay prompts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from backend.security.config import get_security_config


@dataclass
class InjectionPattern:
    """A detected injection pattern."""

    pattern_type: str  # override, escape, jailbreak
    pattern_name: str  # human-readable pattern name
    matched_text: str  # the actual matched text
    confidence: float  # 0.0 to 1.0 confidence score
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    position: tuple[int, int]  # (start, end) in text


@dataclass
class InjectionDetectionReport:
    """Report of injection detection analysis."""

    is_injection_detected: bool
    patterns_found: list[InjectionPattern]
    highest_confidence: float
    highest_severity: str
    total_matches: int

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for logging."""
        return {
            "is_injection_detected": self.is_injection_detected,
            "patterns_found": len(self.patterns_found),
            "highest_confidence": round(self.highest_confidence, 2),
            "highest_severity": self.highest_severity,
            "pattern_types": list(
                set(p.pattern_type for p in self.patterns_found)
            ),
        }


class InjectionDetector:
    """Detects prompt injection attacks in input context."""

    # Override patterns: attempts to redirect system instructions
    OVERRIDE_PATTERNS = {
        "ignore_instructions": {
            "patterns": [
                r"(?i)(ignore|forget|disregard|skip).{0,20}(all\s+)?previous(ly)?\s+(instructions|prompt|context|guidance)",
                r"(?i)(ignore|forget|disregard|skip).{0,20}(the\s+)?(system|original)\s+(instructions|prompt|context)",
            ],
            "severity": "CRITICAL",
            "confidence": 0.95,
        },
        "new_instructions": {
            "patterns": [
                r"(?i)(new\s+)?instructions?:\s+.{10,}",
                r"(?i)your\s+(new\s+)?role\s+is\s+.{10,}",
                r"(?i)you\s+are\s+now\s+.{10,}",
            ],
            "severity": "HIGH",
            "confidence": 0.85,
        },
        "system_prompt_override": {
            "patterns": [
                r"(?i)(system\s+)?prompt\s*(override|change|become|is)[:\s].{10,}",
                r"(?i)treat\s+this\s+as\s+the\s+(new\s+)?(system\s+)?prompt",
            ],
            "severity": "CRITICAL",
            "confidence": 0.9,
        },
    }

    # Escape patterns: attempts to break out of context
    ESCAPE_PATTERNS = {
        "code_escape": {
            "patterns": [
                r"```\s*(system|prompt|instructions)",
                r"<!--\s*(SYSTEM|PROMPT|INSTRUCTIONS)",
                r"{{.*?(system|prompt|instructions).*?}}",
            ],
            "severity": "HIGH",
            "confidence": 0.85,
        },
        "comment_escape": {
            "patterns": [
                r"<!--.*?(system|prompt|instructions).*?-->",
                r"//\s*(system|prompt|instructions|ignore|override)",
            ],
            "severity": "MEDIUM",
            "confidence": 0.75,
        },
    }

    # Jailbreak patterns: attempts to change AI behavior/constraints
    JAILBREAK_PATTERNS = {
        "dan_jailbreak": {
            "patterns": [
                r"(?i)D\.A\.N\.|Do\s+Anything\s+Now",
                r"(?i)unrestricted\s+(AI|mode|version)",
            ],
            "severity": "HIGH",
            "confidence": 0.88,
        },
        "roleplay_jailbreak": {
            "patterns": [
                r"(?i)(roleplay\s+|pretend|act\s+as)\s+(an\s+)?(unfiltered|unrestricted|evil|hacker|attacker)",
                r"(?i)(imagine\s+you\s+are|suppose\s+you\s+are|in\s+a\s+world\s+where)\s+(an\s+)?(unfiltered|unrestricted|evil)",
            ],
            "severity": "MEDIUM",
            "confidence": 0.8,
        },
        "constraint_removal": {
            "patterns": [
                r"(?i)(ignore|remove|disable|bypass|disable).{0,20}(safety|filter|restriction|constraint|guideline)",
                r"(?i)(without|no)\s+(safety|filter|restriction|constraint)",
            ],
            "severity": "HIGH",
            "confidence": 0.82,
        },
    }

    def __init__(self) -> None:
        self.config = get_security_config()
        self._compiled_patterns: dict[str, list[tuple[str, re.Pattern, dict]]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile all regex patterns for efficiency."""
        all_patterns = {
            "override": self.OVERRIDE_PATTERNS,
            "escape": self.ESCAPE_PATTERNS,
            "jailbreak": self.JAILBREAK_PATTERNS,
        }

        for pattern_type, patterns in all_patterns.items():
            self._compiled_patterns[pattern_type] = []
            for pattern_name, pattern_info in patterns.items():
                for pattern_str in pattern_info.get("patterns", []):
                    try:
                        compiled = re.compile(pattern_str)
                        self._compiled_patterns[pattern_type].append(
                            (pattern_name, compiled, pattern_info)
                        )
                    except Exception:
                        pass  # Skip invalid patterns

    def detect(self, text: str) -> InjectionDetectionReport:
        """Scan text for prompt injection patterns."""
        if not text:
            return InjectionDetectionReport(
                is_injection_detected=False,
                patterns_found=[],
                highest_confidence=0.0,
                highest_severity="LOW",
                total_matches=0,
            )

        detected_patterns: list[InjectionPattern] = []
        highest_confidence = 0.0
        highest_severity = "LOW"

        try:
            for pattern_type, patterns in self._compiled_patterns.items():
                for pattern_name, compiled_pattern, pattern_info in patterns:
                    matches = compiled_pattern.finditer(text)
                    for match in matches:
                        confidence = pattern_info.get("confidence", 0.5)
                        severity = pattern_info.get("severity", "MEDIUM")

                        detected_patterns.append(
                            InjectionPattern(
                                pattern_type=pattern_type,
                                pattern_name=pattern_name,
                                matched_text=match.group(0)[:100],  # Truncate for logging
                                confidence=confidence,
                                severity=severity,
                                position=(match.start(), match.end()),
                            )
                        )

                        # Track highest confidence and severity
                        if confidence > highest_confidence:
                            highest_confidence = confidence

                        severity_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
                        if severity_rank.get(severity, 0) > severity_rank.get(
                            highest_severity, 0
                        ):
                            highest_severity = severity

        except Exception:
            # Fail silent: if scanning fails, assume no injection
            pass

        is_injection = len(detected_patterns) > 0 and highest_confidence >= self.config.injection_confidence_threshold

        return InjectionDetectionReport(
            is_injection_detected=is_injection,
            patterns_found=detected_patterns,
            highest_confidence=highest_confidence,
            highest_severity=highest_severity if detected_patterns else "LOW",
            total_matches=len(detected_patterns),
        )


def get_injection_detector() -> InjectionDetector:
    """Get the injection detector instance."""
    return InjectionDetector()
