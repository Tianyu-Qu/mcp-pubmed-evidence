from __future__ import annotations

import httpx
import pytest
from pydantic import HttpUrl

from mcp_pubmed_evidence.bibtex import article_to_bibtex
from mcp_pubmed_evidence.citation import (
    citation_quality_warnings,
    enrich_article_with_crossref_doi,
    is_valid_doi,
    normalize_doi,
)
from mcp_pubmed_evidence.models import PubMedArticle


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
    }
    data.update(updates)
    return PubMedArticle(**data)


def test_normalize_doi_handles_urls_prefixes_case_and_punctuation() -> None:
    assert normalize_doi("https://doi.org/10.1000/ABC.DEF.") == "10.1000/abc.def"
    assert normalize_doi("doi: 10.5555/Test-DOI") == "10.5555/test-doi"
    assert normalize_doi("https://dx.doi.org/10.7777/Example)") == "10.7777/example"


def test_normalize_doi_rejects_invalid_values() -> None:
    assert normalize_doi("not a doi") is None
    assert is_valid_doi("10.1000/example") is True
    assert is_valid_doi("example") is False


def test_citation_quality_warnings_reports_incomplete_metadata() -> None:
    article = make_article(authors=[], journal=None, year=None, doi=None)

    assert citation_quality_warnings(article) == [
        "missing DOI",
        "missing authors",
        "missing journal",
        "missing publication year",
    ]


def test_article_to_bibtex_normalizes_doi() -> None:
    article = make_article(doi="https://doi.org/10.1000/ABC.DEF")

    bibtex = article_to_bibtex(article)

    assert "doi = {10.1000/abc.def}" in bibtex


def test_article_to_bibtex_includes_quality_warning_comment() -> None:
    article = make_article(authors=[], journal=None, year=None, doi=None)

    bibtex = article_to_bibtex(article)

    assert bibtex.startswith("% Citation warnings for PMID 12345678: missing DOI")
    assert "@article{pubmedndmachine12345678" in bibtex


class CrossrefClient:
    async def get(self, *args: object, **kwargs: object) -> httpx.Response:
        payload = {
            "message": {
                "items": [
                    {
                        "DOI": "10.1000/CROSSREF.DOI",
                        "title": ["Machine learning for Alzheimer disease risk prediction"],
                    }
                ]
            }
        }
        return httpx.Response(
            200,
            json=payload,
            request=httpx.Request("GET", "https://api.crossref.org/works"),
        )


@pytest.mark.asyncio
async def test_enrich_article_with_crossref_doi_fills_missing_doi() -> None:
    article = make_article(doi=None)

    enriched = await enrich_article_with_crossref_doi(
        article,
        client=CrossrefClient(),  # type: ignore[arg-type]
    )

    assert enriched.doi == "10.1000/crossref.doi"
    assert enriched.citation_warnings == []
