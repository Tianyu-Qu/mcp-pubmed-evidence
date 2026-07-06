"""Build a unified PubMed + ClinicalTrials.gov evidence table locally.

Usage:
    python examples/build_biomedical_evidence_table.py \
        --query "Alzheimer disease machine learning" \
        --condition "Alzheimer disease" \
        --max-pubmed-results 2 \
        --max-trial-results 2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from mcp_pubmed_evidence.evidence_table import build_biomedical_evidence_table  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a unified evidence table from PubMed and ClinicalTrials.gov."
    )
    parser.add_argument("--query", default=None, help="PubMed query and optional trial query")
    parser.add_argument("--condition", default=None, help="ClinicalTrials.gov condition filter")
    parser.add_argument(
        "--intervention", default=None, help="ClinicalTrials.gov intervention filter"
    )
    parser.add_argument(
        "--max-pubmed-results", type=int, default=3, help="Maximum PubMed records"
    )
    parser.add_argument(
        "--max-trial-results", type=int, default=3, help="Maximum trial records"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON rows instead of a compact text table",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    rows = await build_biomedical_evidence_table(
        query=args.query,
        condition=args.condition,
        intervention=args.intervention,
        max_pubmed_results=args.max_pubmed_results,
        max_trial_results=args.max_trial_results,
    )

    payload = [row.model_dump(mode="json") for row in rows]
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print(f"Rows: {len(rows)}")
    print()
    for index, row in enumerate(rows, start=1):
        print(f"{index}. [{row.source_type}] {row.title or row.source_id}")
        print(f"   ID: {row.source_id}")
        print(f"   Date: {row.year_or_start_date or 'unknown'}")
        print(f"   Study type: {row.study_type or 'unknown'}")
        print(f"   Status: {row.status or 'not applicable'}")
        print(f"   Phase: {row.phase or 'not applicable'}")
        print(f"   Conditions: {', '.join(row.conditions) or 'not available'}")
        print(f"   Interventions: {', '.join(row.interventions) or 'not available'}")
        print(f"   DOI: {row.doi or 'not available'}")
        print(f"   URL: {row.url}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
