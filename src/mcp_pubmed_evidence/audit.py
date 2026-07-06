"""Optional local audit logging for MCP tool calls."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

AUDIT_LOG_ENV_VAR = "MCP_PUBMED_EVIDENCE_AUDIT_LOG"

SENSITIVE_TEXT_FIELDS = {"query", "condition", "intervention", "abstract", "eligibility"}


def audit_tool_call(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    status: str,
    result_summary: dict[str, Any] | None = None,
    error_type: str | None = None,
) -> None:
    """Write one audit event when audit logging is explicitly enabled."""

    path = os.getenv(AUDIT_LOG_ENV_VAR)
    if not path:
        return

    event = {
        "timestamp": datetime.now(UTC).isoformat(),
        "tool_name": tool_name,
        "status": status,
        "arguments": _sanitize_arguments(arguments),
        "result_summary": result_summary or {},
    }
    if error_type:
        event["error_type"] = error_type

    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def _sanitize_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    sanitized = {}
    for key, value in arguments.items():
        if key in SENSITIVE_TEXT_FIELDS:
            sanitized[key] = _summarize_text(value)
        elif isinstance(value, list):
            sanitized[key] = {"count": len(value)}
        else:
            sanitized[key] = value
    return sanitized


def _summarize_text(value: Any) -> dict[str, Any]:
    if value is None:
        return {"present": False, "length": 0}
    text = str(value)
    return {"present": bool(text), "length": len(text)}
