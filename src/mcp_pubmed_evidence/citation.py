"""Citation metadata quality helpers."""

from __future__ import annotations

import re
from typing import Any

import httpx

from .models import PubMedArticle

CROSSREF_WORKS_URL = "https://api.crossref.org/works"
DOI_PATTERN = re.compile(r"10\.\d{4,9}/\S+", flags=re.IGNORECASE)
TRAILING_DOI_PUNCTUATION = ".,;:)]}"


class CrossrefError(RuntimeError):
    """Raised when Crossref cannot return usable metadata."""


def normalize_doi(value: str | None) -> str | None:
    """Normalize DOI strings from PubMed, Crossref, URLs, or copied citations."""

    if not value:
        return None
    candidate = " ".join(value.strip().split())
    candidate = re.sub(r"^doi:\s*", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"^https?://(dx\.)?doi\.org/", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"^https?://doi\.org/", "", candidate, flags=re.IGNORECASE)
    match = DOI_PATTERN.search(candidate)
    if not match:
        return None
    return match.group(0).rstrip(TRAILING_DOI_PUNCTUATION).lower()


def is_valid_doi(value: str | None) -> bool:
    """Return whether a DOI can be normalized into a valid DOI shape."""

    return normalize_doi(value) is not None


def citation_quality_warnings(article: PubMedArticle) -> list[str]:
    """Return citation-quality warnings for incomplete or weak metadata."""

    warnings = []
    if not article.doi:
        warnings.append("missing DOI")
    elif not is_valid_doi(article.doi):
        warnings.append("invalid DOI")
    if not article.authors:
        warnings.append("missing authors")
    if not article.journal:
        warnings.append("missing journal")
    if article.year is None:
        warnings.append("missing publication year")
    return warnings


def article_with_citation_warnings(article: PubMedArticle) -> PubMedArticle:
    """Return an article with citation warnings refreshed from current metadata."""

    return article.model_copy(
        update={"citation_warnings": citation_quality_warnings(article)}
    )


async def enrich_article_with_crossref_doi(
    article: PubMedArticle,
    *,
    client: httpx.AsyncClient | None = None,
) -> PubMedArticle:
    """Fill a missing DOI from Crossref when a confident title match is available."""

    if article.doi:
        return article_with_citation_warnings(article)

    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=20.0)
    try:
        doi = await _find_crossref_doi(active_client, article)
    finally:
        if owns_client:
            await active_client.aclose()

    if not doi:
        return article_with_citation_warnings(article)

    return article_with_citation_warnings(article.model_copy(update={"doi": doi}))


async def _find_crossref_doi(
    client: httpx.AsyncClient,
    article: PubMedArticle,
) -> str | None:
    try:
        response = await client.get(
            CROSSREF_WORKS_URL,
            params={
                "query.bibliographic": article.title,
                "rows": "3",
                "select": "DOI,title,published-print,published-online,container-title",
            },
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise CrossrefError("Crossref DOI lookup timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise CrossrefError(
            f"Crossref DOI lookup failed with HTTP {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise CrossrefError("Crossref DOI lookup failed") from exc

    return _extract_matching_crossref_doi(response.json(), article)


def _extract_matching_crossref_doi(payload: dict[str, Any], article: PubMedArticle) -> str | None:
    items = payload.get("message", {}).get("items", [])
    if not isinstance(items, list):
        return None

    normalized_title = _normalize_title(article.title)
    for item in items:
        if not isinstance(item, dict):
            continue
        titles = item.get("title") or []
        title = titles[0] if titles else ""
        if _normalize_title(title) != normalized_title:
            continue
        doi = normalize_doi(item.get("DOI"))
        if doi:
            return doi
    return None


def _normalize_title(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
