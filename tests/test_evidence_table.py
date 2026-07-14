from __future__ import annotations

import pytest
from pydantic import HttpUrl

from mcp_pubmed_evidence.evidence_table import (
    build_biomedical_evidence_table,
    evidence_rows_to_markdown,
    pubmed_article_to_evidence_row,
    sort_and_filter_evidence_rows,
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
        citation_warnings=["missing DOI"],
    )

    row = pubmed_article_to_evidence_row(article)

    assert row.source_type == "pubmed"
    assert row.source_id == "12345678"
    assert row.title == "Machine learning for Alzheimer disease risk prediction"
    assert row.year_or_start_date == "2024"
    assert row.study_type == "Journal Article"
    assert row.normalized_study_design == "journal_article"
    assert row.normalized_status == "published"
    assert row.evidence_level == "context"
    assert row.doi == "10.1000/example"
    assert str(row.url) == "https://pubmed.ncbi.nlm.nih.gov/12345678/"
    assert row.provenance.source_name == "PubMed"
    assert row.provenance.pmid == "12345678"
    assert row.provenance.nct_id is None
    assert row.citation_warnings == ["missing DOI"]


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
    assert row.normalized_study_design == "interventional_trial"
    assert row.status == "RECRUITING"
    assert row.normalized_status == "active"
    assert row.evidence_level == "trial_record_active"
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


def test_pubmed_randomized_trial_design_is_normalized() -> None:
    article = PubMedArticle(
        pmid="12345678",
        title="Randomized trial",
        authors=[],
        journal="Example Journal",
        year=2024,
        publication_date="2024",
        article_types=["Journal Article", "Randomized Controlled Trial"],
        doi=None,
        abstract=None,
        pubmed_url=HttpUrl("https://pubmed.ncbi.nlm.nih.gov/12345678/"),
    )

    row = pubmed_article_to_evidence_row(article)

    assert row.normalized_study_design == "randomized_trial"
    assert row.evidence_level == "moderate"


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


def test_sort_and_filter_evidence_rows_filters_and_sorts() -> None:
    article_2021 = pubmed_article_to_evidence_row(
        PubMedArticle(
            pmid="11111111",
            title="Older article",
            authors=[],
            journal="Example Journal",
            year=2021,
            publication_date="2021",
            article_types=["Journal Article"],
            doi=None,
            abstract=None,
            pubmed_url=HttpUrl("https://pubmed.ncbi.nlm.nih.gov/11111111/"),
        )
    )
    article_2024 = pubmed_article_to_evidence_row(
        PubMedArticle(
            pmid="22222222",
            title="Newer article",
            authors=[],
            journal="Example Journal",
            year=2024,
            publication_date="2024",
            article_types=["Journal Article"],
            doi=None,
            abstract=None,
            pubmed_url=HttpUrl("https://pubmed.ncbi.nlm.nih.gov/22222222/"),
        )
    )
    trial = trial_to_evidence_row(
        TrialSearchRecord(
            nct_id="NCT12345678",
            brief_title="Trial",
            status="COMPLETED",
            phase="PHASE2",
            study_type="INTERVENTIONAL",
            clinicaltrials_url=HttpUrl("https://clinicaltrials.gov/study/NCT12345678"),
        )
    )

    rows = sort_and_filter_evidence_rows(
        [article_2021, trial, article_2024],
        source_types=["pubmed"],
        sort_by="year_desc",
    )

    assert [row.source_id for row in rows] == ["22222222", "11111111"]


def test_evidence_rows_to_markdown_exports_table() -> None:
    row = pubmed_article_to_evidence_row(
        PubMedArticle(
            pmid="12345678",
            title="Article with | pipe",
            authors=[],
            journal="Example Journal",
            year=2024,
            publication_date="2024",
            article_types=["Journal Article"],
            doi="10.1000/example",
            abstract=None,
            pubmed_url=HttpUrl("https://pubmed.ncbi.nlm.nih.gov/12345678/"),
        )
    )

    markdown = evidence_rows_to_markdown([row])

    assert "| Source | ID | Year/Start | Design | Status | Phase | Title | DOI | URL |" in markdown
    assert "Article with \\| pipe" in markdown
    assert "journal_article" in markdown


@pytest.mark.asyncio
async def test_build_biomedical_evidence_table_requires_input() -> None:
    with pytest.raises(ValueError, match="at least one"):
        await build_biomedical_evidence_table()
