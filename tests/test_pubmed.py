from __future__ import annotations

import pytest

from mcp_pubmed_evidence.bibtex import article_to_bibtex
from mcp_pubmed_evidence.pubmed import (
    _build_query,
    _normalize_max_results,
    _parse_pubmed_xml,
    _require_query,
    build_evidence_table,
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


def test_require_query_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="query must not be empty"):
        _require_query("   ")


def test_normalize_max_results_caps_large_values() -> None:
    assert _normalize_max_results(500) == 50


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
    assert "BACKGROUND: Risk prediction matters." in article.abstract
    assert "Validation Study" in article.article_types
    assert str(article.pubmed_url) == "https://pubmed.ncbi.nlm.nih.gov/12345678/"


def test_build_evidence_table_returns_compact_rows() -> None:
    article = _parse_pubmed_xml(SAMPLE_XML)[0]

    rows = build_evidence_table([article])

    assert len(rows) == 1
    assert rows[0].pmid == "12345678"
    assert rows[0].doi == "10.1000/example.doi"


def test_article_to_bibtex_includes_core_fields() -> None:
    article = _parse_pubmed_xml(SAMPLE_XML)[0]

    bibtex = article_to_bibtex(article)

    assert bibtex.startswith("@article{smith2024machine12345678")
    assert "title = {Machine learning for Alzheimer disease risk prediction}" in bibtex
    assert "author = {Jane Smith and Wei Chen}" in bibtex
    assert "doi = {10.1000/example.doi}" in bibtex
    assert "pmid = {12345678}" in bibtex
