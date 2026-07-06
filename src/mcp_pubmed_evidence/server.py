"""MCP server exposing PubMed evidence tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .bibtex import articles_to_bibtex
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


@mcp.tool()
async def search_pubmed(
    query: str,
    max_results: int = 10,
    year_from: int | None = None,
    year_to: int | None = None,
    article_types: list[str] | None = None,
) -> dict:
    """Search PubMed and return normalized article metadata with source URLs."""

    result = await search_pubmed_core(
        query=query,
        max_results=max_results,
        year_from=year_from,
        year_to=year_to,
        article_types=article_types,
    )
    return result.model_dump(mode="json")


@mcp.tool()
async def get_pubmed_article(pmid: str) -> dict:
    """Fetch normalized metadata for one PubMed article by PMID."""

    article = await fetch_pubmed_article(pmid)
    return article.model_dump(mode="json")


@mcp.tool()
async def get_abstract(pmid: str) -> dict:
    """Fetch the abstract for one PubMed article by PMID with citation provenance."""

    article = await fetch_pubmed_article(pmid)
    return {
        "pmid": article.pmid,
        "title": article.title,
        "abstract": article.abstract,
        "doi": article.doi,
        "pubmed_url": str(article.pubmed_url),
    }


@mcp.tool()
async def export_bibtex(pmids: list[str]) -> str:
    """Export PubMed articles as BibTeX entries."""

    articles = [await fetch_pubmed_article(pmid) for pmid in pmids]
    return articles_to_bibtex(articles)


@mcp.tool()
async def build_evidence_table(pmids: list[str]) -> list[dict]:
    """Build a compact evidence table from PubMed IDs."""

    articles = [await fetch_pubmed_article(pmid) for pmid in pmids]
    rows = build_evidence_table_rows(articles)
    return [row.model_dump(mode="json") for row in rows]


def main() -> None:
    """Run the MCP server over stdio."""

    mcp.run()


if __name__ == "__main__":
    main()
