from __future__ import annotations

import pytest
from pydantic import HttpUrl

from mcp_pubmed_evidence.evidence_table import (
    build_biomedical_evidence_table,
    pubmed_article_to_evidence_row,
    trial_to_evidence_row,
)
from mcp_pubmed_evidence.models import PubMedArticle
from mcp_pubmed_evidence.trial_models import TrialOutcome, TrialSearchRecord, TrialSummary


def test_pubmed_article_to_evidence_row_preserves_provenance() -> None:
    article = PubMedArticle(
        pmid="12345678",
        title="Machine learning for Alzheimer disease risk prediction",
        authors=["Jane Smith"],
        journal="Example Journal",
        year=2024,
        publication_date="2024 Jan",
        article_types=["Journal Article", "Validation Study"],
        doi="10.1000/example",
        abstract="Example abstract.",
        pubmed_url=HttpUrl("https://pubmed.ncbi.nlm.nih.gov/12345678/"),
    )

    row = pubmed_article_to_evidence_row(article)

    assert row.source_type == "pubmed"
    assert row.source_id == "12345678"
    assert row.title == "Machine learning for Alzheimer disease risk prediction"
    assert row.year_or_start_date == "2024"
    assert row.study_type == "Journal Article"
    assert row.doi == "10.1000/example"
    assert str(row.url) == "https://pubmed.ncbi.nlm.nih.gov/12345678/"
    assert row.provenance.source_name == "PubMed"
    assert row.provenance.pmid == "12345678"
    assert row.provenance.nct_id is None


def test_trial_search_record_to_evidence_row_preserves_trial_fields() -> None:
    trial = TrialSearchRecord(
        nct_id="NCT12345678",
        brief_title="GLP-1 for Cognitive Decline",
        official_title="A Trial of GLP-1 Therapy for Cognitive Decline",
        status="RECRUITING",
        phase="PHASE2",
        study_type="INTERVENTIONAL",
        conditions=["Alzheimer Disease"],
        interventions=["Semaglutide"],
        enrollment=120,
        start_date="2025-01",
        completion_date="2028-12",
        last_update_posted="2026-06-01",
        clinicaltrials_url=HttpUrl("https://clinicaltrials.gov/study/NCT12345678"),
    )

    row = trial_to_evidence_row(trial)

    assert row.source_type == "clinical_trial"
    assert row.source_id == "NCT12345678"
    assert row.title == "GLP-1 for Cognitive Decline"
    assert row.year_or_start_date == "2025-01"
    assert row.study_type == "INTERVENTIONAL"
    assert row.status == "RECRUITING"
    assert row.phase == "PHASE2"
    assert row.conditions == ["Alzheimer Disease"]
    assert row.interventions == ["Semaglutide"]
    assert row.outcomes == []
    assert row.provenance.source_name == "ClinicalTrials.gov"
    assert row.provenance.nct_id == "NCT12345678"


def test_trial_summary_to_evidence_row_includes_outcomes() -> None:
    trial = TrialSummary(
        nct_id="NCT12345678",
        brief_title="GLP-1 for Cognitive Decline",
        official_title="A Trial of GLP-1 Therapy for Cognitive Decline",
        status="COMPLETED",
        phase="PHASE2",
        study_type="INTERVENTIONAL",
        conditions=["Alzheimer Disease"],
        interventions=["Semaglutide"],
        enrollment=120,
        start_date="2025-01",
        completion_date="2028-12",
        last_update_posted="2026-06-01",
        clinicaltrials_url=HttpUrl("https://clinicaltrials.gov/study/NCT12345678"),
        primary_outcomes=[TrialOutcome(measure="Cognitive score change")],
        secondary_outcomes=[TrialOutcome(description="Safety events")],
    )

    row = trial_to_evidence_row(trial)

    assert row.outcomes == ["Cognitive score change", "Safety events"]


class PubMedResultStub:
    def __init__(self, articles: list[PubMedArticle]):
        self.articles = articles


class TrialResultStub:
    def __init__(self, trials: list[TrialSearchRecord]):
        self.trials = trials


@pytest.mark.asyncio
async def test_build_biomedical_evidence_table_combines_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    article = PubMedArticle(
        pmid="12345678",
        title="PubMed article",
        authors=[],
        journal="Example Journal",
        year=2024,
        publication_date="2024",
        article_types=["Journal Article"],
        doi="10.1000/example",
        abstract=None,
        pubmed_url=HttpUrl("https://pubmed.ncbi.nlm.nih.gov/12345678/"),
    )
    trial = TrialSearchRecord(
        nct_id="NCT12345678",
        brief_title="Clinical trial",
        status="RECRUITING",
        phase="PHASE2",
        study_type="INTERVENTIONAL",
        conditions=["Alzheimer Disease"],
        interventions=["Semaglutide"],
        enrollment=120,
        start_date="2025-01",
        clinicaltrials_url=HttpUrl("https://clinicaltrials.gov/study/NCT12345678"),
    )

    async def fake_search_pubmed(**kwargs: object) -> PubMedResultStub:
        return PubMedResultStub([article])

    async def fake_search_trials(**kwargs: object) -> TrialResultStub:
        return TrialResultStub([trial])

    monkeypatch.setattr("mcp_pubmed_evidence.evidence_table.search_pubmed", fake_search_pubmed)
    monkeypatch.setattr("mcp_pubmed_evidence.evidence_table.search_trials", fake_search_trials)

    rows = await build_biomedical_evidence_table(
        query="GLP-1 cognitive decline",
        condition="Alzheimer Disease",
        intervention="Semaglutide",
        max_pubmed_results=1,
        max_trial_results=1,
    )

    assert [row.source_type for row in rows] == ["pubmed", "clinical_trial"]
    assert rows[0].source_id == "12345678"
    assert rows[1].source_id == "NCT12345678"


@pytest.mark.asyncio
async def test_build_biomedical_evidence_table_requires_input() -> None:
    with pytest.raises(ValueError, match="at least one"):
        await build_biomedical_evidence_table()