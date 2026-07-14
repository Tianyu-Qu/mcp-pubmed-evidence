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


def sort_and_filter_evidence_rows(
    rows: list[BiomedicalEvidenceRow],
    *,
    source_types: list[str] | None = None,
    study_designs: list[str] | None = None,
    statuses: list[str] | None = None,
    sort_by: str = "year_desc",
) -> list[BiomedicalEvidenceRow]:
    """Filter and sort unified evidence rows for display or downstream agents."""

    filtered = rows
    if source_types:
        filtered = [row for row in filtered if row.source_type in set(source_types)]
    if study_designs:
        filtered = [
            row for row in filtered if row.normalized_study_design in set(study_designs)
        ]
    if statuses:
        filtered = [row for row in filtered if row.normalized_status in set(statuses)]

    reverse = sort_by in {"year_desc", "source_type_desc"}
    if sort_by in {"year_desc", "year_asc"}:
        return sorted(filtered, key=_row_sort_date, reverse=reverse)
    if sort_by in {"source_type_asc", "source_type_desc"}:
        return sorted(filtered, key=lambda row: (row.source_type, row.source_id), reverse=reverse)
    if sort_by == "title_asc":
        return sorted(filtered, key=lambda row: (row.title or "").lower())
    if sort_by == "evidence_level":
        return sorted(filtered, key=lambda row: _evidence_level_rank(row.evidence_level))
    raise ValueError(
        "sort_by must be year_desc, year_asc, title_asc, evidence_level, "
        "source_type_asc, or source_type_desc"
    )


def evidence_rows_to_markdown(rows: list[BiomedicalEvidenceRow]) -> str:
    """Render unified evidence rows as a compact Markdown table."""

    headers = [
        "Source",
        "ID",
        "Year/Start",
        "Design",
        "Status",
        "Phase",
        "Title",
        "DOI",
        "URL",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        values = [
            row.source_type,
            row.source_id,
            row.year_or_start_date or "",
            row.normalized_study_design,
            row.normalized_status,
            row.phase or "",
            row.title or "",
            row.doi or "",
            str(row.url),
        ]
        lines.append("| " + " | ".join(_escape_markdown_cell(value) for value in values) + " |")
    return "\n".join(lines)


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
        normalized_study_design=_normalize_pubmed_study_design(article.article_types),
        status=None,
        normalized_status="published",
        evidence_level=_pubmed_evidence_level(article.article_types),
        phase=None,
        conditions=[],
        interventions=[],
        outcomes=[],
        doi=article.doi,
        citation_count=article.citation_count,
        is_open_access=article.is_open_access,
        open_access_url=article.open_access_url,
        venue=article.venue,
        normalized_venue=article.normalized_venue,
        url=source_url,
        provenance=EvidenceProvenance(
            source_name="PubMed",
            source_id=article.pmid,
            source_url=source_url,
            doi=article.doi,
            pmid=article.pmid,
            nct_id=None,
        ),
        citation_warnings=article.citation_warnings,
        metadata_warnings=article.metadata_warnings,
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
        normalized_study_design=_normalize_trial_study_design(trial),
        status=trial.status,
        normalized_status=_normalize_trial_status(trial.status),
        evidence_level=_trial_evidence_level(trial),
        phase=trial.phase,
        conditions=trial.conditions,
        interventions=trial.interventions,
        outcomes=outcomes,
        doi=None,
        citation_count=None,
        is_open_access=None,
        open_access_url=None,
        venue=None,
        normalized_venue=None,
        url=source_url,
        provenance=EvidenceProvenance(
            source_name="ClinicalTrials.gov",
            source_id=trial.nct_id,
            source_url=source_url,
            doi=None,
            pmid=None,
            nct_id=trial.nct_id,
        ),
        citation_warnings=[],
        metadata_warnings=[],
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


def _normalize_pubmed_study_design(article_types: list[str]) -> str:
    joined = " ".join(value.lower() for value in article_types)
    if "randomized controlled trial" in joined:
        return "randomized_trial"
    if "systematic review" in joined or "meta-analysis" in joined:
        return "evidence_synthesis"
    if "review" in joined:
        return "review"
    if "observational study" in joined or "cohort" in joined or "case-control" in joined:
        return "observational_study"
    if "clinical trial" in joined:
        return "clinical_trial_publication"
    if "journal article" in joined:
        return "journal_article"
    return "unknown"


def _normalize_trial_study_design(trial: TrialSearchRecord | TrialSummary) -> str:
    study_type = (trial.study_type or "").lower()
    if "interventional" in study_type:
        return "interventional_trial"
    if "observational" in study_type:
        return "observational_trial"
    if "expanded access" in study_type:
        return "expanded_access"
    return "registry_record"


def _normalize_trial_status(status: str | None) -> str:
    value = (status or "").strip().lower().replace("_", " ")
    if value in {"recruiting", "enrolling by invitation", "not yet recruiting"}:
        return "active"
    if value in {"active not recruiting", "available"}:
        return "active_not_recruiting"
    if value in {"completed", "approved for marketing"}:
        return "completed"
    if value in {"terminated", "withdrawn", "suspended", "no longer available"}:
        return "stopped"
    if value:
        return value.replace(" ", "_")
    return "unknown"


def _pubmed_evidence_level(article_types: list[str]) -> str:
    design = _normalize_pubmed_study_design(article_types)
    if design == "evidence_synthesis":
        return "high"
    if design in {"randomized_trial", "clinical_trial_publication"}:
        return "moderate"
    if design in {"observational_study", "journal_article", "review"}:
        return "context"
    return "unknown"


def _trial_evidence_level(trial: TrialSearchRecord | TrialSummary) -> str:
    design = _normalize_trial_study_design(trial)
    status = _normalize_trial_status(trial.status)
    if design == "interventional_trial" and status == "completed":
        return "trial_record_completed"
    if design == "interventional_trial":
        return "trial_record_active"
    if design == "observational_trial":
        return "registry_context"
    return "registry_record"


def _row_sort_date(row: BiomedicalEvidenceRow) -> tuple[int, str]:
    value = row.year_or_start_date or ""
    year = 0
    for token in value.replace("-", " ").split():
        if token.isdigit() and len(token) == 4:
            year = int(token)
            break
    return year, row.source_id


def _evidence_level_rank(value: str) -> int:
    order = {
        "high": 0,
        "moderate": 1,
        "trial_record_completed": 2,
        "trial_record_active": 3,
        "context": 4,
        "registry_context": 5,
        "registry_record": 6,
        "unknown": 7,
    }
    return order.get(value, 8)


def _escape_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
