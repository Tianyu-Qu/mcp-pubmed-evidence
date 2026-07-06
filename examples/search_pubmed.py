"""Run a small PubMed search without an MCP client.

Usage:
    python examples/search_pubmed.py "Alzheimer disease machine learning" --max-results 3
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from mcp_pubmed_evidence.pubmed import search_pubmed  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search PubMed and print normalized results.")
    parser.add_argument("query", help="PubMed search query")
    parser.add_argument("--max-results", type=int, default=3, help="Maximum number of results")
    parser.add_argument("--year-from", type=int, default=None, help="Publication year lower bound")
    parser.add_argument("--year-to", type=int, default=None, help="Publication year upper bound")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    result = await search_pubmed(
        query=args.query,
        max_results=args.max_results,
        year_from=args.year_from,
        year_to=args.year_to,
    )

    print(f"Query: {result.query}")
    print(f"Results: {result.count}")
    print()
    for index, article in enumerate(result.articles, start=1):
        print(f"{index}. {article.title}")
        print(f"   PMID: {article.pmid}")
        print(f"   Year: {article.year or 'unknown'}")
        print(f"   Journal: {article.journal or 'unknown'}")
        print(f"   DOI: {article.doi or 'not available'}")
        print(f"   URL: {article.pubmed_url}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
