from __future__ import annotations

import pytest

from mcp_pubmed_evidence.safety import validate_research_query


def test_validate_research_query_normalizes_whitespace() -> None:
    assert (
        validate_research_query(
            "  Alzheimer   disease   machine learning  ",
            field_name="query",
            required=True,
        )
        == "Alzheimer disease machine learning"
    )


def test_validate_research_query_rejects_empty_required_value() -> None:
    with pytest.raises(ValueError, match="query must not be empty"):
        validate_research_query("   ", field_name="query", required=True)


def test_validate_research_query_rejects_overlong_value() -> None:
    with pytest.raises(ValueError, match="500 characters or fewer"):
        validate_research_query("a" * 501, field_name="query", required=True)


def test_validate_research_query_rejects_personal_medical_advice() -> None:
    with pytest.raises(ValueError, match="personal medical advice"):
        validate_research_query(
            "Should I take donepezil for my symptoms?",
            field_name="query",
            required=True,
        )


def test_validate_research_query_allows_research_terms() -> None:
    assert (
        validate_research_query(
            "diagnosis and treatment biomarkers in Alzheimer disease",
            field_name="query",
            required=True,
        )
        == "diagnosis and treatment biomarkers in Alzheimer disease"
    )
