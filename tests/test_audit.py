from __future__ import annotations

import json

from mcp_pubmed_evidence.audit import AUDIT_LOG_ENV_VAR, audit_tool_call


def test_audit_tool_call_is_disabled_by_default(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.delenv(AUDIT_LOG_ENV_VAR, raising=False)
    log_path = tmp_path / "audit.jsonl"

    audit_tool_call(
        tool_name="search_pubmed",
        arguments={"query": "Alzheimer disease"},
        status="success",
        result_summary={"returned_count": 1},
    )

    assert not log_path.exists()


def test_audit_tool_call_writes_sanitized_jsonl(monkeypatch, tmp_path) -> None:
    log_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv(AUDIT_LOG_ENV_VAR, str(log_path))

    audit_tool_call(
        tool_name="search_pubmed",
        arguments={
            "query": "Alzheimer disease machine learning",
            "pmids": ["12345678", "87654321"],
            "max_results": 2,
        },
        status="success",
        result_summary={"returned_count": 2},
    )

    event = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert event["tool_name"] == "search_pubmed"
    assert event["status"] == "success"
    assert event["arguments"]["query"] == {"present": True, "length": 34}
    assert event["arguments"]["pmids"] == {"count": 2}
    assert event["arguments"]["max_results"] == 2
    assert event["result_summary"] == {"returned_count": 2}
    assert "Alzheimer disease machine learning" not in log_path.read_text(encoding="utf-8")
