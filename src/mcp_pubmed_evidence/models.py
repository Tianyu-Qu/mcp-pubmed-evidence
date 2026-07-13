"""Structured data models returned by the PubMed MCP tools."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class ResultMetadata(BaseModel):
    """Metadata describing result limits and truncation."""

    source_name: str | None = None
    source_url: str | None = None
    query_summary: dict[str, Any] = Field(default_factory=dict)
    requested_max_results: int
    effective_max_results: int
    max_allowed_results: int
    returned_count: int
    total_available: int | None = None
    truncated: bool = False


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
    citation_warnings: list[str] = Field(default_factory=list)


class PubMedSearchResult(BaseModel):
    """Search response containing normalized articles and provenance."""

    query: str
    count: int
    metadata: ResultMetadata
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
    citation_warnings: list[str] = Field(default_factory=list)
