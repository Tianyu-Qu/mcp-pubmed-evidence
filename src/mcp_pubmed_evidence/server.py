"""MCP server exposing biomedical evidence tools."""

from __future__ import annotations

from collections import Counter
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.fastmcp import FastMCP

from .audit import audit_tool_call
from .bibtex import articles_to_bibtex
from .clinicaltrials import (
    MAX_RESULTS_LIMIT as TRIAL_MAX_RESULTS_LIMIT,
)
from .clinicaltrials import (
    get_trial_summary as fetch_trial_summary,
)
from .clinicaltrials import (
    map_trial_to_publications as map_trial_publications_core,
)
from .clinicaltrials import (
    search_trials as search_trials_core,
)
from .evidence_models import BiomedicalEvidenceRow
from .evidence_table import build_biomedical_evidence_table as build_biomedical_table_core
from .pubmed import (
    MAX_RESULTS_LIMIT as PUBMED_MAX_RESULTS_LIMIT,
)
from .pubmed import (
    build_evidence_table as build_evidence_table_rows,
)
from .pubmed import (
    get_pubmed_article as fetch_pubmed_article,
)
from .pubmed import (
    search_pubmed as search_pubmed_core,
)

mcp = FastMCP("mcp-pubmed-evidence")


async def _run_audited(
    tool_name: str,
    arguments: dict[str, Any],
    operation: Callable[[], Awaitable[Any]],
) -> Any:
    try:
        result = await operation()
    except Exception as exc:
        audit_tool_call(
            tool_name=tool_name,
            arguments=arguments,
            status="error",
            error_type=type(exc).__name__,
        )
        raise

    audit_tool_call(
        tool_name=tool_name,
        arguments=arguments,
        status="success",
        result_summary=_summarize_result(result),
    )
    return result


def _summarize_result(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        metadata = result.get("metadata")
        if isinstance(metadata, dict):
            return {
                "returned_count": metadata.get("returned_count", result.get("count")),
                "truncated": metadata.get("truncated"),
                "source_counts": metadata.get("source_counts"),
            }
        if "count" in result:
            return {"returned_count": result.get("count")}
        if "rows" in result and isinstance(result["rows"], list):
            return {"returned_count": len(result["rows"])}
    if isinstance(result, list):
        return {"returned_count": len(result)}
    if isinstance(result, str):
        return {"result_type": "text", "length": len(result)}
    return {"result_type": type(result).__name__}


def _build_source_summary(rows: list[BiomedicalEvidenceRow]) -> list[dict]:
    """Summarize row provenance at the response level."""

    grouped: dict[str, dict] = {}
    for row in rows:
        source_name = row.provenance.source_name
        summary = grouped.setdefault(
            source_name,
            {
                "source_name": source_name,
                "source_type": row.source_type,
                "source_url": str(row.provenance.source_url),
                "count": 0,
                "source_ids": [],
            },
        )
        summary["count"] += 1
        summary["source_ids"].append(row.source_id)
    return list(grouped.values())


@mcp.tool()
async def search_pubmed(
    query: str,
    max_results: int = 10,
    year_from: int | None = None,
    year_to: int | None = None,
    article_types: list[str] | None = None,
) -> dict:
    """Search PubMed and return normalized article metadata with source URLs."""

    async def operation() -> dict:
        result = await search_pubmed_core(
            query=query,
            max_results=max_results,
            year_from=year_from,
            year_to=year_to,
            article_types=article_types,
        )
        return result.model_dump(mode="json")

    return await _run_audited(
        "search_pubmed",
        {
            "query": query,
            "max_results": max_results,
            "year_from": year_from,
            "year_to": year_to,
            "article_types": article_types or [],
        },
        operation,
    )


@mcp.tool()
async def get_pubmed_article(pmid: str) -> dict:
    """Fetch normalized metadata for one PubMed article by PMID."""

    async def operation() -> dict:
        article = await fetch_pubmed_article(pmid)
        return article.model_dump(mode="json")

    return await _run_audited("get_pubmed_article", {"pmid": pmid}, operation)


@mcp.tool()
async def get_abstract(pmid: str) -> dict:
    """Fetch the abstract for one PubMed article by PMID with citation provenance."""

    async def operation() -> dict:
        article = await fetch_pubmed_article(pmid)
        return {
            "pmid": article.pmid,
            "title": article.title,
            "abstract": article.abstract,
            "doi": article.doi,
            "pubmed_url": str(article.pubmed_url),
        }

    return await _run_audited("get_abstract", {"pmid": pmid}, operation)


@mcp.tool()
async def export_bibtex(pmids: list[str]) -> str:
    """Export PubMed articles as BibTeX entries."""

    async def operation() -> str:
        articles = [await fetch_pubmed_article(pmid) for pmid in pmids]
        return articles_to_bibtex(articles)

    return await _run_audited("export_bibtex", {"pmids": pmids}, operation)


@mcp.tool()
async def build_evidence_table(pmids: list[str]) -> list[dict]:
    """Build a compact evidence table from PubMed IDs."""

    async def operation() -> list[dict]:
        articles = [await fetch_pubmed_article(pmid) for pmid in pmids]
        rows = build_evidence_table_rows(articles)
        return [row.model_dump(mode="json") for row in rows]

    return await _run_audited("build_evidence_table", {"pmids": pmids}, operation)


@mcp.tool()
async def search_trials(
    query: str | None = None,
    condition: str | None = None,
    intervention: str | None = None,
    status: str | None = None,
    max_results: int = 10,
) -> dict:
    """Search ClinicalTrials.gov and return normalized trial records."""

    async def operation() -> dict:
        result = await search_trials_core(
            query=query,
            condition=condition,
            intervention=intervention,
            status=status,
            max_results=max_results,
        )
        return result.model_dump(mode="json")

    return await _run_audited(
        "search_trials",
        {
            "query": query,
            "condition": condition,
            "intervention": intervention,
            "status": status,
            "max_results": max_results,
        },
        operation,
    )


@mcp.tool()
async def get_trial_summary(nct_id: str) -> dict:
    """Fetch a detailed ClinicalTrials.gov trial summary by NCT ID."""

    async def operation() -> dict:
        summary = await fetch_trial_summary(nct_id)
        return summary.model_dump(mode="json")

    return await _run_audited("get_trial_summary", {"nct_id": nct_id}, operation)


@mcp.tool()
async def map_trial_to_publications(nct_id: str) -> dict:
    """Map a ClinicalTrials.gov NCT ID to linked PubMed articles when available."""

    async def operation() -> dict:
        publication_map = await map_trial_publications_core(nct_id)
        return publication_map.model_dump(mode="json")

    return await _run_audited("map_trial_to_publications", {"nct_id": nct_id}, operation)


@mcp.tool()
async def build_biomedical_evidence_table(
    query: str | None = None,
    condition: str | None = None,
    intervention: str | None = None,
    max_pubmed_results: int = 10,
    max_trial_results: int = 10,
) -> dict:
    """Build a unified evidence table from PubMed and ClinicalTrials.gov results."""

    async def operation() -> dict:
        rows = await build_biomedical_table_core(
            query=query,
            condition=condition,
            intervention=intervention,
            max_pubmed_results=max_pubmed_results,
            max_trial_results=max_trial_results,
        )
        source_counts = Counter(row.source_type for row in rows)
        return {
            "metadata": {
                "query_summary": {
                    "query": query,
                    "condition": condition,
                    "intervention": intervention,
                },
                "sources_used": _build_source_summary(rows),
                "source_counts": dict(source_counts),
                "requested_max_pubmed_results": max_pubmed_results,
                "requested_max_trial_results": max_trial_results,
                "effective_max_pubmed_results": min(
                    max_pubmed_results, PUBMED_MAX_RESULTS_LIMIT
                ),
                "effective_max_trial_results": min(
                    max_trial_results, TRIAL_MAX_RESULTS_LIMIT
                ),
                "max_allowed_pubmed_results": PUBMED_MAX_RESULTS_LIMIT,
                "max_allowed_trial_results": TRIAL_MAX_RESULTS_LIMIT,
                "returned_count": len(rows),
                "truncated": (
                    max_pubmed_results > PUBMED_MAX_RESULTS_LIMIT
                    or max_trial_results > TRIAL_MAX_RESULTS_LIMIT
                ),
            },
            "rows": [row.model_dump(mode="json") for row in rows],
        }

    return await _run_audited(
        "build_biomedical_evidence_table",
        {
            "query": query,
            "condition": condition,
            "intervention": intervention,
            "max_pubmed_results": max_pubmed_results,
            "max_trial_results": max_trial_results,
        },
        operation,
    )


def main() -> None:
    """Run the MCP server over stdio."""

    mcp.run()


if __name__ == "__main__":
    main()
