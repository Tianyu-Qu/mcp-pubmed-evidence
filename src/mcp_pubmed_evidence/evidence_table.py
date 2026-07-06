"""Converters and builders for unified biomedical evidence table rows."""

from __future__ import annotations

from .clinicaltrials import search_trials
from .evidence_models import BiomedicalEvidenceRow, EvidenceProvenance
from .models import PubMedArticle
from .pubmed import search_pubmed
from .trial_models import TrialSearchRecord, TrialSummary


async def build_biomedical_evidence_table(
    query: str | None = None,
    condition: str | None = None,
    intervention: str | None = None,
    max_pubmed_results: int = 10,
    max_trial_results: int = 10,
) -> list[BiomedicalEvidenceRow]:
    """Build a unified evidence table from PubMed and ClinicalTrials.gov results."""

    if not any([query, condition, intervention]):
        raise ValueError("at least one of query, condition, or intervention must be provided")

    rows: list[BiomedicalEvidenceRow] = []
    if query:
        pubmed_result = await search_pubmed(query=query, max_results=max_pubmed_results)
        rows.extend(pubmed_article_to_evidence_row(article) for article in pubmed_result.articles)

    if condition or intervention:
        trial_result = await search_trials(
            query=query,
            condition=condition,
            intervention=intervention,
            max_results=max_trial_results,
        )
        rows.extend(trial_to_evidence_row(trial) for trial in trial_result.trials)

    return rows


def pubmed_article_to_evidence_row(article: PubMedArticle) -> BiomedicalEvidenceRow:
    """Convert a normalized PubMed article to a unified evidence row."""

    source_url = article.pubmed_url
    return BiomedicalEvidenceRow(
        source_type="pubmed",
        source_id=article.pmid,
        title=article.title,
        year_or_start_date=(
            str(article.year) if article.year is not None else article.publication_date
        ),
        study_type=_first_or_none(article.article_types),
        status=None,
        phase=None,
        conditions=[],
        interventions=[],
        outcomes=[],
        doi=article.doi,
        url=source_url,
        provenance=EvidenceProvenance(
            source_name="PubMed",
            source_id=article.pmid,
            source_url=source_url,
            doi=article.doi,
            pmid=article.pmid,
            nct_id=None,
        ),
    )


def trial_to_evidence_row(trial: TrialSearchRecord | TrialSummary) -> BiomedicalEvidenceRow:
    """Convert a ClinicalTrials.gov trial record to a unified evidence row."""

    source_url = trial.clinicaltrials_url
    outcomes = _trial_outcome_labels(trial) if isinstance(trial, TrialSummary) else []
    return BiomedicalEvidenceRow(
        source_type="clinical_trial",
        source_id=trial.nct_id,
        title=trial.brief_title or trial.official_title,
        year_or_start_date=trial.start_date,
        study_type=trial.study_type,
        status=trial.status,
        phase=trial.phase,
        conditions=trial.conditions,
        interventions=trial.interventions,
        outcomes=outcomes,
        doi=None,
        url=source_url,
        provenance=EvidenceProvenance(
            source_name="ClinicalTrials.gov",
            source_id=trial.nct_id,
            source_url=source_url,
            doi=None,
            pmid=None,
            nct_id=trial.nct_id,
        ),
    )


def _trial_outcome_labels(trial: TrialSummary) -> list[str]:
    labels = []
    for outcome in [*trial.primary_outcomes, *trial.secondary_outcomes]:
        label = outcome.measure or outcome.description
        if label:
            labels.append(label)
    return labels


def _first_or_none(values: list[str]) -> str | None:
    return values[0] if values else None
