"""Safety-oriented validation helpers for biomedical research queries."""

from __future__ import annotations

import re

MAX_QUERY_LENGTH = 500

PERSONAL_MEDICAL_ADVICE_PATTERNS = [
    re.compile(pattern, flags=re.IGNORECASE)
    for pattern in [
        r"\bdiagnose\s+(me|my)\b",
        r"\bwhat\s+do\s+i\s+have\b",
        r"\bshould\s+i\s+(take|use|stop)\b",
        r"\bcan\s+i\s+(take|use|stop)\b",
        r"\btreat\s+my\b",
        r"\bmy\s+symptoms\b",
        r"\bprescribe\s+(me|my)\b",
    ]
]


def validate_research_query(
    value: str | None,
    *,
    field_name: str,
    required: bool = False,
) -> str | None:
    """Validate a user-provided biomedical research query field."""

    normalized = " ".join(value.split()) if value else ""
    if not normalized:
        if required:
            raise ValueError(f"{field_name} must not be empty")
        return None

    if len(normalized) > MAX_QUERY_LENGTH:
        raise ValueError(
            f"{field_name} must be {MAX_QUERY_LENGTH} characters or fewer"
        )

    if any(pattern.search(normalized) for pattern in PERSONAL_MEDICAL_ADVICE_PATTERNS):
        raise ValueError(
            f"{field_name} appears to ask for personal medical advice; "
            "this tool only supports biomedical research evidence retrieval"
        )

    return normalized
