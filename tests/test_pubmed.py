from __future__ import annotations

import httpx
import pytest

from mcp_pubmed_evidence.bibtex import article_to_bibtex
from mcp_pubmed_evidence.pubmed import (
    PubMedError,
    _build_query,
    _fetch_articles,
    _normalize_max_results,
    _parse_pubmed_xml,
    _require_query,
    _search_pmids,
    build_evidence_table,
    get_pubmed_article,
    search_pubmed,
)

SAMPLE_XML = """<?xml version="1.0" ?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345678</PMID>
      <Article>
        <Journal>
          <JournalIssue>
            <PubDate>
              <Year>2024</Year>
              <Month>Jan</Month>
            </PubDate>
          </JournalIssue>
          <Title>Journal of Biomedical Evidence</Title>
        </Journal>
        <ArticleTitle>Machine learning for Alzheimer disease risk prediction</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND">Risk prediction matters.</AbstractText>
          <AbstractText Label="METHODS">We trained a model.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author>
            <LastName>Smith</LastName>
            <ForeName>Jane</ForeName>
          </Author>
          <Author>
            <LastName>Chen</LastName>
            <ForeName>Wei</ForeName>
          </Author>
        </AuthorList>
        <PublicationTypeList>
          <PublicationType>Journal Article</PublicationType>
          <PublicationType>Validation Study</PublicationType>
        </PublicationTypeList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">12345678</ArticleId>
        <ArticleId IdType="doi">10.1000/example.doi</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""

MISSING_OPTIONAL_XML = """<?xml version="1.0" ?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>87654321</PMID>
      <Article>
        <Journal>
          <JournalIssue>
            <PubDate>
              <MedlineDate>Winter 1999</MedlineDate>
            </PubDate>
          </JournalIssue>
        </Journal>
        <ArticleTitle>Article without optional metadata</ArticleTitle>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""

EMPTY_XML = """<?xml version="1.0" ?>
<PubmedArticleSet />
"""


class TimeoutClient:
    async def get(self, *args: object, **kwargs: object) -> httpx.Response:
        raise httpx.TimeoutException("timeout")


class HttpErrorClient:
    async def get(self, *args: object, **kwargs: object) -> httpx.Response:
        request = httpx.Request("GET", "https://example.test")
        return httpx.Response(500, request=request)


def test_require_query_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="query must not be empty"):
        _require_query("   ")


def test_require_query_rejects_personal_medical_advice() -> None:
    with pytest.raises(ValueError, match="personal medical advice"):
        _require_query("diagnose me with Alzheimer disease")


@pytest.mark.asyncio
async def test_get_pubmed_article_rejects_invalid_pmid() -> None:
    with pytest.raises(ValueError, match="pmid must be a non-empty numeric string"):
        await get_pubmed_article("not-a-pmid")


def test_normalize_max_results_caps_large_values() -> None:
    assert _normalize_max_results(500) == 50


@pytest.mark.asyncio
async def test_search_pubmed_reports_truncation_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    article = _parse_pubmed_xml(SAMPLE_XML)[0]

    async def fake_search_pmids(
        client: httpx.AsyncClient, query: str, max_results: int
    ) -> tuple[list[str], int]:
        assert max_results == 50
        return ["12345678"], 200

    async def fake_fetch_articles(
        client: httpx.AsyncClient, pmids: list[str]
    ) -> list[object]:
        return [article]

    monkeypatch.setattr("mcp_pubmed_evidence.pubmed._search_pmids", fake_search_pmids)
    monkeypatch.setattr("mcp_pubmed_evidence.pubmed._fetch_articles", fake_fetch_articles)

    result = await search_pubmed("Alzheimer disease", max_results=500)

    assert result.metadata.requested_max_results == 500
    assert result.metadata.source_name == "PubMed"
    assert result.metadata.source_url == "https://pubmed.ncbi.nlm.nih.gov/"
    assert result.metadata.query_summary["query"] == "Alzheimer disease"
    assert result.metadata.query_summary["normalized_query"] == "Alzheimer disease"
    assert result.metadata.effective_max_results == 50
    assert result.metadata.max_allowed_results == 50
    assert result.metadata.returned_count == 1
    assert result.metadata.total_available == 200
    assert result.metadata.truncated is True


def test_build_query_adds_year_and_article_type_filters() -> None:
    query = _build_query(
        "Alzheimer disease",
        year_from=2020,
        year_to=2024,
        article_types=["Randomized Controlled Trial", "Review"],
    )

    assert "Alzheimer disease" in query
    assert "2020" in query
    assert "2024" in query
    assert "Randomized Controlled Trial" in query
    assert "Review" in query


def test_build_query_rejects_invalid_year_range() -> None:
    with pytest.raises(ValueError, match="year_from"):
        _build_query("Alzheimer", year_from=2025, year_to=2020, article_types=None)


def test_parse_pubmed_xml_normalizes_article() -> None:
    articles = _parse_pubmed_xml(SAMPLE_XML)

    assert len(articles) == 1
    article = articles[0]
    assert article.pmid == "12345678"
    assert article.title == "Machine learning for Alzheimer disease risk prediction"
    assert article.authors == ["Jane Smith", "Wei Chen"]
    assert article.journal == "Journal of Biomedical Evidence"
    assert article.year == 2024
    assert article.publication_date == "2024 Jan"
    assert article.doi == "10.1000/example.doi"
    assert article.citation_warnings == []
    assert article.metadata_sources == ["PubMed"]
    assert article.normalized_venue == "journal of biomedical evidence"
    assert "BACKGROUND: Risk prediction matters." in article.abstract
    assert "Validation Study" in article.article_types
    assert str(article.pubmed_url) == "https://pubmed.ncbi.nlm.nih.gov/12345678/"


def test_parse_pubmed_xml_handles_missing_optional_fields() -> None:
    article = _parse_pubmed_xml(MISSING_OPTIONAL_XML)[0]

    assert article.pmid == "87654321"
    assert article.title == "Article without optional metadata"
    assert article.authors == []
    assert article.journal is None
    assert article.year == 1999
    assert article.publication_date == "Winter 1999"
    assert article.article_types == []
    assert article.doi is None
    assert article.abstract is None
    assert article.citation_warnings == ["missing DOI", "missing authors", "missing journal"]


def test_parse_pubmed_xml_returns_empty_list_for_no_results() -> None:
    assert _parse_pubmed_xml(EMPTY_XML) == []


def test_parse_pubmed_xml_raises_on_invalid_xml() -> None:
    with pytest.raises(PubMedError, match="invalid XML"):
        _parse_pubmed_xml("<not-valid")


def test_build_evidence_table_returns_compact_rows() -> None:
    article = _parse_pubmed_xml(SAMPLE_XML)[0]

    rows = build_evidence_table([article])

    assert len(rows) == 1
    assert rows[0].pmid == "12345678"
    assert rows[0].doi == "10.1000/example.doi"
    assert rows[0].citation_warnings == []


def test_article_to_bibtex_includes_core_fields() -> None:
    article = _parse_pubmed_xml(SAMPLE_XML)[0]

    bibtex = article_to_bibtex(article)

    assert bibtex.startswith("@article{smith2024machine12345678")
    assert "title = {Machine learning for Alzheimer disease risk prediction}" in bibtex
    assert "author = {Jane Smith and Wei Chen}" in bibtex
    assert "doi = {10.1000/example.doi}" in bibtex
    assert "pmid = {12345678}" in bibtex


@pytest.mark.asyncio
async def test_get_pubmed_article_raises_when_no_article_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_articles(client: httpx.AsyncClient, pmids: list[str]) -> list[object]:
        return []

    monkeypatch.setattr("mcp_pubmed_evidence.pubmed._fetch_articles", fake_fetch_articles)

    with pytest.raises(PubMedError, match="No PubMed article found"):
        await get_pubmed_article("12345678")


@pytest.mark.asyncio
async def test_search_pmids_wraps_timeout() -> None:
    with pytest.raises(PubMedError, match="timed out"):
        await _search_pmids(TimeoutClient(), "Alzheimer", 1)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_fetch_articles_wraps_http_error() -> None:
    with pytest.raises(PubMedError, match="HTTP 500"):
        await _fetch_articles(HttpErrorClient(), ["12345678"])  # type: ignore[arg-type]
