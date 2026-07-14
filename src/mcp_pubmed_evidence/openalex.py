"""OpenAlex metadata enrichment helpers."""

from __future__ import annotations

import re
from typing import Any

import httpx

from .citation import normalize_doi
from .models import PubMedArticle

OPENALEX_WORKS_URL = "https://api.openalex.org/works"


class OpenAlexError(RuntimeError):
    """Raised when OpenAlex cannot return usable metadata."""


def normalize_venue(value: str | None) -> str | None:
    """Normalize journal or venue names for lightweight comparison."""

    if not value:
        return None
    normalized = value.lower().replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split()) or None


async def enrich_article_with_openalex(
    article: PubMedArticle,
    *,
    client: httpx.AsyncClient | None = None,
) -> PubMedArticle:
    """Enrich an article with OpenAlex metadata using DOI lookup."""

    doi = normalize_doi(article.doi)
    if not doi:
        return _with_source(article, "PubMed")

    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=20.0)
    try:
        payload = await _fetch_openalex_work_by_doi(active_client, doi)
    finally:
        if owns_client:
            await active_client.aclose()

    if not payload:
        return _with_warning(
            _with_source(article, "PubMed"),
            "OpenAlex DOI lookup returned no record",
        )
    return _merge_openalex_metadata(article, payload)


async def _fetch_openalex_work_by_doi(
    client: httpx.AsyncClient,
    doi: str,
) -> dict[str, Any] | None:
    try:
        response = await client.get(f"{OPENALEX_WORKS_URL}/https://doi.org/{doi}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise OpenAlexError("OpenAlex DOI lookup timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise OpenAlexError(
            f"OpenAlex DOI lookup failed with HTTP {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise OpenAlexError("OpenAlex DOI lookup failed") from exc

    payload = response.json()
    if not isinstance(payload, dict):
        raise OpenAlexError("OpenAlex returned unexpected JSON")
    return payload


def _merge_openalex_metadata(article: PubMedArticle, payload: dict[str, Any]) -> PubMedArticle:
    openalex_doi = normalize_doi(payload.get("doi"))
    warnings = list(article.metadata_warnings)
    if article.doi and openalex_doi and normalize_doi(article.doi) != openalex_doi:
        warnings.append("OpenAlex DOI differs from PubMed DOI")

    venue = _extract_venue(payload)
    normalized_venue = normalize_venue(venue)
    pubmed_venue = normalize_venue(article.journal)
    if pubmed_venue and normalized_venue and pubmed_venue != normalized_venue:
        warnings.append("OpenAlex venue differs from PubMed journal")

    open_access = payload.get("open_access") if isinstance(payload.get("open_access"), dict) else {}
    return article.model_copy(
        update={
            "doi": normalize_doi(article.doi) or openalex_doi,
            "citation_count": _int_or_none(payload.get("cited_by_count")),
            "is_open_access": open_access.get("is_oa"),
            "open_access_url": open_access.get("oa_url"),
            "venue": venue or article.venue,
            "normalized_venue": normalized_venue or normalize_venue(article.journal),
            "metadata_sources": _append_unique(article.metadata_sources, ["PubMed", "OpenAlex"]),
            "metadata_warnings": warnings,
        }
    )


def _extract_venue(payload: dict[str, Any]) -> str | None:
    primary_location = payload.get("primary_location")
    if not isinstance(primary_location, dict):
        return None
    source = primary_location.get("source")
    if not isinstance(source, dict):
        return None
    display_name = source.get("display_name")
    return display_name if isinstance(display_name, str) and display_name.strip() else None


def _with_source(article: PubMedArticle, source: str) -> PubMedArticle:
    return article.model_copy(
        update={"metadata_sources": _append_unique(article.metadata_sources, [source])}
    )


def _with_warning(article: PubMedArticle, warning: str) -> PubMedArticle:
    warnings = list(article.metadata_warnings)
    if warning not in warnings:
        warnings.append(warning)
    return article.model_copy(update={"metadata_warnings": warnings})


def _append_unique(values: list[str], additions: list[str]) -> list[str]:
    result = list(values)
    for value in additions:
        if value not in result:
            result.append(value)
    return result


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None
