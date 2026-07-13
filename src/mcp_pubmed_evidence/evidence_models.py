"""Unified biomedical evidence table models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class EvidenceProvenance(BaseModel):
    """Source provenance for one evidence row."""

    source_name: str
    source_id: str
    source_url: HttpUrl
    doi: str | None = None
    pmid: str | None = None
    nct_id: str | None = None


class BiomedicalEvidenceRow(BaseModel):
    """Unified evidence row for PubMed articles and clinical trial records."""

    source_type: Literal["pubmed", "clinical_trial"]
    source_id: str
    title: str | None = None
    year_or_start_date: str | None = None
    study_type: str | None = None
    status: str | None = None
    phase: str | None = None
    conditions: list[str] = Field(default_factory=list)
    interventions: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    doi: str | None = None
    url: HttpUrl
    provenance: EvidenceProvenance
    citation_warnings: list[str] = Field(default_factory=list)
