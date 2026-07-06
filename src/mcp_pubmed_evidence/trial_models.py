"""Structured data models returned by ClinicalTrials.gov tools."""

from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl

from .models import ResultMetadata


class TrialOutcome(BaseModel):
    """Normalized clinical trial outcome."""

    measure: str | None = None
    description: str | None = None
    time_frame: str | None = None


class TrialReference(BaseModel):
    """Publication or registry reference linked from ClinicalTrials.gov."""

    citation: str | None = None
    pmid: str | None = None
    type: str | None = None


class TrialSearchRecord(BaseModel):
    """Compact trial record returned by trial search."""

    nct_id: str
    brief_title: str | None = None
    official_title: str | None = None
    status: str | None = None
    phase: str | None = None
    study_type: str | None = None
    conditions: list[str] = Field(default_factory=list)
    interventions: list[str] = Field(default_factory=list)
    enrollment: int | None = None
    start_date: str | None = None
    completion_date: str | None = None
    last_update_posted: str | None = None
    clinicaltrials_url: HttpUrl


class TrialSearchResult(BaseModel):
    """Search response containing normalized trial records."""

    query: str | None = None
    condition: str | None = None
    intervention: str | None = None
    status: str | None = None
    count: int
    metadata: ResultMetadata
    trials: list[TrialSearchRecord]


class TrialSummary(TrialSearchRecord):
    """Detailed normalized ClinicalTrials.gov trial record."""

    brief_summary: str | None = None
    detailed_description: str | None = None
    arms: list[str] = Field(default_factory=list)
    primary_outcomes: list[TrialOutcome] = Field(default_factory=list)
    secondary_outcomes: list[TrialOutcome] = Field(default_factory=list)
    eligibility: str | None = None
    locations: list[str] = Field(default_factory=list)
    sponsor: str | None = None
    collaborators: list[str] = Field(default_factory=list)
    references: list[TrialReference] = Field(default_factory=list)
    result_references: list[TrialReference] = Field(default_factory=list)


class TrialPublicationMap(BaseModel):
    """Mapping between one trial and linked PubMed publications."""

    nct_id: str
    linked_pmids: list[str] = Field(default_factory=list)
    references: list[TrialReference] = Field(default_factory=list)
    result_references: list[TrialReference] = Field(default_factory=list)
    pubmed_articles: list[dict] = Field(default_factory=list)
