"""Run a small ClinicalTrials.gov search without an MCP client.

Usage:
    python examples/search_trials.py --condition "Alzheimer disease" --intervention "GLP-1"
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

from mcp_pubmed_evidence.clinicaltrials import search_trials  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search ClinicalTrials.gov and print trial records."
    )
    parser.add_argument("--query", default=None, help="General trial search query")
    parser.add_argument("--condition", default=None, help="Condition or disease")
    parser.add_argument("--intervention", default=None, help="Intervention, drug, or device")
    parser.add_argument("--status", default=None, help="Overall recruitment status")
    parser.add_argument("--max-results", type=int, default=5, help="Maximum number of results")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    result = await search_trials(
        query=args.query,
        condition=args.condition,
        intervention=args.intervention,
        status=args.status,
        max_results=args.max_results,
    )

    print(f"Condition: {result.condition or 'any'}")
    print(f"Intervention: {result.intervention or 'any'}")
    print(f"Results: {result.count}")
    print()
    for index, trial in enumerate(result.trials, start=1):
        print(f"{index}. {trial.brief_title or trial.official_title or trial.nct_id}")
        print(f"   NCT ID: {trial.nct_id}")
        print(f"   Status: {trial.status or 'unknown'}")
        print(f"   Phase: {trial.phase or 'not available'}")
        print(f"   Study type: {trial.study_type or 'unknown'}")
        print(f"   Enrollment: {trial.enrollment or 'not available'}")
        print(f"   Conditions: {', '.join(trial.conditions) or 'not available'}")
        print(f"   Interventions: {', '.join(trial.interventions) or 'not available'}")
        print(f"   URL: {trial.clinicaltrials_url}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
