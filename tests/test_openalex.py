from __future__ import annotations

import httpx
import pytest
from pydantic import HttpUrl

from mcp_pubmed_evidence.models import PubMedArticle
from mcp_pubmed_evidence.openalex import enrich_article_with_openalex, normalize_venue


def make_article(**updates: object) -> PubMedArticle:
    data = {
        "pmid": "12345678",
        "title": "Machine learning for Alzheimer disease risk prediction",
        "authors": ["Jane Smith"],
        "journal": "Journal of Biomedical Evidence",
        "year": 2024,
        "publication_date": "2024 Jan",
        "article_types": ["Journal Article"],
        "doi": "10.1000/example",
        "abstract": None,
        "pubmed_url": HttpUrl("https://pubmed.ncbi.nlm.nih.gov/12345678/"),
        "metadata_sources": ["PubMed"],
    }
    data.update(updates)
    return PubMedArticle(**data)


class OpenAlexClient:
    def __init__(self, payload: dict):
        self.payload = payload

    async def get(self, *args: object, **kwargs: object) -> httpx.Response:
        return httpx.Response(
            200,
            json=self.payload,
            request=httpx.Request("GET", "https://api.openalex.org/works/doi"),
        )


def test_normalize_venue_standardizes_names() -> None:
    assert normalize_venue("International Journal & Molecular Sciences") == (
        "international journal and molecular sciences"
    )


@pytest.mark.asyncio
async def test_enrich_article_with_openalex_adds_counts_open_access_and_venue() -> None:
    article = make_article()
    payload = {
        "doi": "https://doi.org/10.1000/example",
        "cited_by_count": 42,
        "open_access": {
            "is_oa": True,
            "oa_url": "https://example.org/open.pdf",
        },
        "primary_location": {
            "source": {"display_name": "Journal of Biomedical Evidence"}
        },
    }

    enriched = await enrich_article_with_openalex(
        article,
        client=OpenAlexClient(payload),  # type: ignore[arg-type]
    )

    assert enriched.citation_count == 42
    assert enriched.is_open_access is True
    assert enriched.open_access_url == "https://example.org/open.pdf"
    assert enriched.venue == "Journal of Biomedical Evidence"
    assert enriched.normalized_venue == "journal of biomedical evidence"
    assert enriched.metadata_sources == ["PubMed", "OpenAlex"]
    assert enriched.metadata_warnings == []


@pytest.mark.asyncio
async def test_enrich_article_with_openalex_warns_on_venue_mismatch() -> None:
    article = make_article(journal="PubMed Journal")
    payload = {
        "doi": "https://doi.org/10.1000/example",
        "cited_by_count": 1,
        "open_access": {"is_oa": False},
        "primary_location": {"source": {"display_name": "Different Journal"}},
    }

    enriched = await enrich_article_with_openalex(
        article,
        client=OpenAlexClient(payload),  # type: ignore[arg-type]
    )

    assert "OpenAlex venue differs from PubMed journal" in enriched.metadata_warnings


@pytest.mark.asyncio
async def test_enrich_article_with_openalex_skips_missing_doi() -> None:
    article = make_article(doi=None)

    enriched = await enrich_article_with_openalex(article)

    assert enriched.metadata_sources == ["PubMed"]
    assert enriched.citation_count is None
