"""Structured data models returned by the PubMed MCP tools."""

from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class PubMedArticle(BaseModel):
    """Normalized metadata for one PubMed article."""

    pmid: str = Field(..., description="PubMed identifier")
    title: str
    authors: list[str] = Field(default_factory=list)
    journal: str | None = None
    year: int | None = None
    publication_date: str | None = None
    article_types: list[str] = Field(default_factory=list)
    doi: str | None = None
    abstract: str | None = None
    pubmed_url: HttpUrl


class PubMedSearchResult(BaseModel):
    """Search response containing normalized articles and provenance."""

    query: str
    count: int
    articles: list[PubMedArticle]


class EvidenceTableRow(BaseModel):
    """Compact row for evidence tables consumed by agents or humans."""

    pmid: str
    year: int | None
    title: str
    journal: str | None
    article_types: list[str]
    doi: str | None
    pubmed_url: HttpUrl
