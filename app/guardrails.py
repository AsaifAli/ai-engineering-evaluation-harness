from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .config import MAX_INPUT_CHARS, MIN_CONFIDENCE_FOR_ACTION


@dataclass
class GuardrailResult:
    text: str
    injection_detected: bool
    redactions: int
    reasons: list[str]


INJECTION_PATTERNS = [
    r"ignore (all|any|the) previous instructions",
    r"ignore (all|any|the) prior instructions",
    r"system prompt",
    r"developer message",
    r"reveal (the|your) (system|developer) prompt",
    r"jailbreak",
    r"bypass (the|your) guardrails",
    r"disregard (all|the) rules",
    r"follow my instructions instead",
]

SECRET_PATTERNS = [
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}"), "Bearer [REDACTED_TOKEN]"),
]


def sanitize_untrusted_text(value: str) -> GuardrailResult:
    text = (value or "")[:MAX_INPUT_CHARS]
    lower = text.lower()
    reasons = [pattern for pattern in INJECTION_PATTERNS if re.search(pattern, lower)]
    redactions = 0
    for regex, replacement in SECRET_PATTERNS:
        text, count = regex.subn(replacement, text)
        redactions += count
    if len(value or "") > MAX_INPUT_CHARS:
        reasons.append("input_truncated")
    return GuardrailResult(
        text=text,
        injection_detected=bool(reasons),
        redactions=redactions,
        reasons=reasons,
    )


def guardrail_status(result: GuardrailResult) -> str:
    if result.injection_detected:
        return "flagged"
    if result.redactions:
        return "sanitized"
    return "passed"


def policy_for_action(*, injection_detected: bool, confidence: float | None = None) -> dict[str, Any]:
    reasons: list[str] = []
    if injection_detected:
        reasons.append("prompt-injection-signal")
    if confidence is not None and confidence < MIN_CONFIDENCE_FOR_ACTION:
        reasons.append("low-confidence")
    return {
        "action_allowed": not bool(reasons),
        "requires_human_approval": True,
        "action_scope": "manual_review_only" if reasons else "bounded_engineering_action",
        "policy_reasons": reasons,
    }
