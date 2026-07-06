from __future__ import annotations

import pytest
from pydantic import HttpUrl

from mcp_pubmed_evidence.evidence_models import BiomedicalEvidenceRow, EvidenceProvenance
from mcp_pubmed_evidence.models import PubMedArticle
from mcp_pubmed_evidence.server import build_biomedical_evidence_table, get_abstract


@pytest.mark.asyncio
async def test_get_abstract_returns_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_pubmed_article(pmid: str) -> PubMedArticle:
        return PubMedArticle(
            pmid=pmid,
            title="Example article",
            authors=["Jane Smith"],
            journal="Example Journal",
            year=2024,
            publication_date="2024 Jan",
            article_types=["Journal Article"],
            doi="10.1000/example",
            abstract="This is an example abstract.",
            pubmed_url=HttpUrl(f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"),
        )

    monkeypatch.setattr(
        "mcp_pubmed_evidence.server.fetch_pubmed_article",
        fake_fetch_pubmed_article,
    )

    result = await get_abstract("12345678")

    assert result == {
        "pmid": "12345678",
        "title": "Example article",
        "abstract": "This is an example abstract.",
        "doi": "10.1000/example",
        "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
    }


@pytest.mark.asyncio
async def test_build_biomedical_evidence_table_returns_limit_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = BiomedicalEvidenceRow(
        source_type="pubmed",
        source_id="12345678",
        title="Example article",
        year_or_start_date="2024",
        study_type="Journal Article",
        doi="10.1000/example",
        url=HttpUrl("https://pubmed.ncbi.nlm.nih.gov/12345678/"),
        provenance=EvidenceProvenance(
            source_name="PubMed",
            source_id="12345678",
            source_url=HttpUrl("https://pubmed.ncbi.nlm.nih.gov/12345678/"),
            doi="10.1000/example",
            pmid="12345678",
        ),
    )

    async def fake_build_biomedical_table_core(**kwargs: object) -> list[BiomedicalEvidenceRow]:
        return [row]

    monkeypatch.setattr(
        "mcp_pubmed_evidence.server.build_biomedical_table_core",
        fake_build_biomedical_table_core,
    )

    result = await build_biomedical_evidence_table(
        query="Alzheimer disease",
        max_pubmed_results=500,
        max_trial_results=2,
    )

    assert result["metadata"]["requested_max_pubmed_results"] == 500
    assert result["metadata"]["query_summary"] == {
        "query": "Alzheimer disease",
        "condition": None,
        "intervention": None,
    }
    assert result["metadata"]["source_counts"] == {"pubmed": 1}
    assert result["metadata"]["sources_used"] == [
        {
            "source_name": "PubMed",
            "source_type": "pubmed",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
            "count": 1,
            "source_ids": ["12345678"],
        }
    ]
    assert result["metadata"]["effective_max_pubmed_results"] == 50
    assert result["metadata"]["max_allowed_pubmed_results"] == 50
    assert result["metadata"]["returned_count"] == 1
    assert result["metadata"]["truncated"] is True
    assert result["rows"][0]["source_id"] == "12345678"
