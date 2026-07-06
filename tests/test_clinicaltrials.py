from __future__ import annotations

import httpx
import pytest

from mcp_pubmed_evidence.clinicaltrials import (
    ClinicalTrialsError,
    _build_search_params,
    _get_json,
    _parse_trial_summary,
    _require_nct_id,
    map_trial_to_publications,
    search_trials,
)
from mcp_pubmed_evidence.models import PubMedArticle

TRIAL_STUDY = {
    "protocolSection": {
        "identificationModule": {
            "nctId": "NCT12345678",
            "briefTitle": "GLP-1 for Cognitive Decline",
            "officialTitle": "A Trial of GLP-1 Therapy for Cognitive Decline",
        },
        "statusModule": {
            "overallStatus": "RECRUITING",
            "startDateStruct": {"date": "2025-01"},
            "completionDateStruct": {"date": "2028-12"},
            "lastUpdatePostDateStruct": {"date": "2026-06-01"},
        },
        "designModule": {
            "studyType": "INTERVENTIONAL",
            "phases": ["PHASE2"],
            "enrollmentInfo": {"count": 120},
        },
        "conditionsModule": {"conditions": ["Alzheimer Disease", "Cognitive Decline"]},
        "armsInterventionsModule": {
            "armGroups": [{"label": "GLP-1"}, {"label": "Placebo"}],
            "interventions": [{"name": "Semaglutide"}],
        },
        "descriptionModule": {
            "briefSummary": "Brief trial summary.",
            "detailedDescription": "Detailed trial description.",
        },
        "outcomesModule": {
            "primaryOutcomes": [
                {
                    "measure": "Cognitive score change",
                    "description": "Change from baseline.",
                    "timeFrame": "12 months",
                }
            ],
            "secondaryOutcomes": [{"measure": "Safety", "timeFrame": "12 months"}],
        },
        "eligibilityModule": {"eligibilityCriteria": "Adults with mild cognitive impairment."},
        "contactsLocationsModule": {
            "locations": [
                {
                    "facility": "Memory Center",
                    "city": "Boston",
                    "state": "MA",
                    "country": "United States",
                }
            ]
        },
        "sponsorCollaboratorsModule": {
            "leadSponsor": {"name": "Example University"},
            "collaborators": [{"name": "Example Hospital"}],
        },
        "referencesModule": {
            "references": [
                {
                    "citation": "Smith J. Example trial publication. PMID: 12345678",
                    "pmid": "12345678",
                    "type": "BACKGROUND",
                }
            ],
            "resultReferences": [
                {
                    "citation": "Chen W. Trial result publication. PMID: 87654321",
                    "type": "RESULT",
                }
            ],
        },
    }
}


class JsonClient:
    def __init__(self, payload: dict):
        self.payload = payload

    async def get(self, *args: object, **kwargs: object) -> httpx.Response:
        return httpx.Response(200, json=self.payload, request=httpx.Request("GET", "https://example.test"))



class ForbiddenClient:
    async def get(self, *args: object, **kwargs: object) -> httpx.Response:
        request = httpx.Request("GET", "https://clinicaltrials.gov/api/v2/studies")
        return httpx.Response(403, text="Forbidden", request=request)

class TimeoutClient:
    async def get(self, *args: object, **kwargs: object) -> httpx.Response:
        raise httpx.TimeoutException("timeout")


def test_require_nct_id_normalizes_valid_id() -> None:
    assert _require_nct_id("nct12345678") == "NCT12345678"


def test_require_nct_id_rejects_invalid_id() -> None:
    with pytest.raises(ValueError, match="NCT"):
        _require_nct_id("bad-id")


def test_build_search_params_maps_filters() -> None:
    params = _build_search_params(
        query="cognition",
        condition="Alzheimer disease",
        intervention="GLP-1",
        status="RECRUITING",
        max_results=5,
    )

    assert params["query.term"] == "cognition"
    assert params["query.cond"] == "Alzheimer disease"
    assert params["query.intr"] == "GLP-1"
    assert params["filter.overallStatus"] == "RECRUITING"
    assert params["pageSize"] == "5"


def test_parse_trial_summary_normalizes_core_fields() -> None:
    summary = _parse_trial_summary(TRIAL_STUDY)

    assert summary.nct_id == "NCT12345678"
    assert summary.brief_title == "GLP-1 for Cognitive Decline"
    assert summary.status == "RECRUITING"
    assert summary.phase == "PHASE2"
    assert summary.study_type == "INTERVENTIONAL"
    assert summary.conditions == ["Alzheimer Disease", "Cognitive Decline"]
    assert summary.interventions == ["Semaglutide"]
    assert summary.enrollment == 120
    assert summary.primary_outcomes[0].measure == "Cognitive score change"
    assert summary.secondary_outcomes[0].measure == "Safety"
    assert summary.locations == ["Memory Center, Boston, MA, United States"]
    assert summary.sponsor == "Example University"
    assert summary.collaborators == ["Example Hospital"]
    assert summary.references[0].pmid == "12345678"
    assert summary.result_references[0].pmid == "87654321"
    assert str(summary.clinicaltrials_url) == "https://clinicaltrials.gov/study/NCT12345678"


@pytest.mark.asyncio
async def test_search_trials_requires_at_least_one_query_field() -> None:
    with pytest.raises(ValueError, match="at least one"):
        await search_trials()


@pytest.mark.asyncio
async def test_search_trials_normalizes_response(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_json(*args: object, **kwargs: object) -> dict:
        return {"studies": [TRIAL_STUDY], "totalCount": 75}

    monkeypatch.setattr("mcp_pubmed_evidence.clinicaltrials._get_json", fake_get_json)

    result = await search_trials(condition="Alzheimer disease", max_results=1)

    assert result.count == 1
    assert result.metadata.source_name == "ClinicalTrials.gov"
    assert result.metadata.source_url == "https://clinicaltrials.gov/"
    assert result.metadata.query_summary["condition"] == "Alzheimer disease"
    assert result.metadata.requested_max_results == 1
    assert result.metadata.effective_max_results == 1
    assert result.metadata.max_allowed_results == 50
    assert result.metadata.returned_count == 1
    assert result.metadata.total_available == 75
    assert result.metadata.truncated is True
    assert result.trials[0].nct_id == "NCT12345678"
    assert result.trials[0].interventions == ["Semaglutide"]


@pytest.mark.asyncio
async def test_get_json_explains_forbidden_network_error() -> None:
    with pytest.raises(ClinicalTrialsError, match="current HTTP client"):
        await _get_json(
            ForbiddenClient(),  # type: ignore[arg-type]
            "/studies",
            params={"format": "json"},
            operation="trial search",
        )


@pytest.mark.asyncio
async def test_search_trials_wraps_timeout() -> None:
    with pytest.raises(ClinicalTrialsError, match="timed out"):
        await _get_json(
            TimeoutClient(),  # type: ignore[arg-type]
            "/studies",
            params={"format": "json"},
            operation="trial search",
        )


@pytest.mark.asyncio
async def test_map_trial_to_publications_fetches_linked_pubmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_trial_summary(nct_id: str):
        return _parse_trial_summary(TRIAL_STUDY)

    async def fake_get_pubmed_article(pmid: str) -> PubMedArticle:
        return PubMedArticle(
            pmid=pmid,
            title=f"Article {pmid}",
            authors=[],
            journal="Example Journal",
            year=2024,
            publication_date="2024",
            article_types=["Journal Article"],
            doi=None,
            abstract=None,
            pubmed_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        )

    monkeypatch.setattr(
        "mcp_pubmed_evidence.clinicaltrials.get_trial_summary",
        fake_get_trial_summary,
    )
    monkeypatch.setattr(
        "mcp_pubmed_evidence.clinicaltrials.get_pubmed_article",
        fake_get_pubmed_article,
    )

    publication_map = await map_trial_to_publications("NCT12345678")

    assert publication_map.linked_pmids == ["12345678", "87654321"]
    assert len(publication_map.pubmed_articles) == 2
    assert publication_map.pubmed_articles[0]["pmid"] == "12345678"
