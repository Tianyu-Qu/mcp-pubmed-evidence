from __future__ import annotations

import pytest
from pydantic import HttpUrl

from mcp_pubmed_evidence.models import PubMedArticle
from mcp_pubmed_evidence.server import get_abstract


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
