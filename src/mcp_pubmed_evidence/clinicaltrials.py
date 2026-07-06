"""ClinicalTrials.gov API client and response normalization."""

from __future__ import annotations

import asyncio
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable

import httpx

from .models import ResultMetadata
from .pubmed import PubMedError, get_pubmed_article
from .trial_models import (
    TrialOutcome,
    TrialPublicationMap,
    TrialReference,
    TrialSearchRecord,
    TrialSearchResult,
    TrialSummary,
)

CLINICALTRIALS_API_BASE_URL = "https://clinicaltrials.gov/api/v2"
DEFAULT_TIMEOUT = 20.0
MAX_RESULTS_LIMIT = 50
USER_AGENT = "mcp-pubmed-evidence/0.2.0"


class ClinicalTrialsError(RuntimeError):
    """Raised when ClinicalTrials.gov cannot return a usable response."""


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _normalize_max_results(max_results: int) -> int:
    if max_results < 1:
        raise ValueError("max_results must be at least 1")
    return min(max_results, MAX_RESULTS_LIMIT)


def _build_result_metadata(
    *,
    query_summary: dict[str, object],
    requested_max_results: int,
    effective_max_results: int,
    returned_count: int,
    total_available: int | None = None,
) -> ResultMetadata:
    return ResultMetadata(
        source_name="ClinicalTrials.gov",
        source_url="https://clinicaltrials.gov/",
        query_summary=query_summary,
        requested_max_results=requested_max_results,
        effective_max_results=effective_max_results,
        max_allowed_results=MAX_RESULTS_LIMIT,
        returned_count=returned_count,
        total_available=total_available,
        truncated=(
            requested_max_results > effective_max_results
            or (total_available is not None and total_available > returned_count)
        ),
    )


def _require_nct_id(nct_id: str) -> str:
    normalized = nct_id.strip().upper()
    if not re.fullmatch(r"NCT\d{8}", normalized):
        raise ValueError("nct_id must look like NCT followed by 8 digits")
    return normalized


async def search_trials(
    query: str | None = None,
    condition: str | None = None,
    intervention: str | None = None,
    status: str | None = None,
    max_results: int = 10,
) -> TrialSearchResult:
    """Search ClinicalTrials.gov and return normalized trial records."""

    if not any(_clean_text(value) for value in [query, condition, intervention]):
        raise ValueError("at least one of query, condition, or intervention must be provided")

    effective_max_results = _normalize_max_results(max_results)
    params = _build_search_params(
        query=query,
        condition=condition,
        intervention=intervention,
        status=status,
        max_results=effective_max_results,
    )

    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        payload = await _get_json(
            client,
            "/studies",
            params=params,
            operation="trial search",
        )

    trials = [_parse_search_record(study) for study in payload.get("studies", [])]
    total_available = _parse_total_available(payload)
    return TrialSearchResult(
        query=query,
        condition=condition,
        intervention=intervention,
        status=status,
        count=len(trials),
        metadata=_build_result_metadata(
            query_summary={
                "query": query,
                "condition": condition,
                "intervention": intervention,
                "status": status,
            },
            requested_max_results=max_results,
            effective_max_results=effective_max_results,
            returned_count=len(trials),
            total_available=total_available,
        ),
        trials=trials,
    )


async def get_trial_summary(nct_id: str) -> TrialSummary:
    """Fetch one ClinicalTrials.gov study by NCT ID."""

    normalized_nct_id = _require_nct_id(nct_id)
    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        study = await _get_json(
            client,
            f"/studies/{normalized_nct_id}",
            params={"format": "json"},
            operation="trial fetch",
        )
    return _parse_trial_summary(study)


async def map_trial_to_publications(nct_id: str) -> TrialPublicationMap:
    """Map a ClinicalTrials.gov NCT ID to linked PubMed articles when available."""

    summary = await get_trial_summary(nct_id)
    linked_pmids = _unique_pmids(summary.references + summary.result_references)
    pubmed_articles: list[dict] = []
    for pmid in linked_pmids:
        try:
            article = await get_pubmed_article(pmid)
        except (PubMedError, ValueError):
            continue
        pubmed_articles.append(article.model_dump(mode="json"))

    return TrialPublicationMap(
        nct_id=summary.nct_id,
        linked_pmids=linked_pmids,
        references=summary.references,
        result_references=summary.result_references,
        pubmed_articles=pubmed_articles,
    )


def _build_search_params(
    *,
    query: str | None,
    condition: str | None,
    intervention: str | None,
    status: str | None,
    max_results: int,
) -> dict[str, str]:
    params = {"format": "json", "pageSize": str(max_results)}
    if query_text := _clean_text(query):
        params["query.term"] = query_text
    if condition_text := _clean_text(condition):
        params["query.cond"] = condition_text
    if intervention_text := _clean_text(intervention):
        params["query.intr"] = intervention_text
    if status_text := _clean_text(status):
        params["filter.overallStatus"] = status_text
    return params


def _parse_total_available(payload: dict) -> int | None:
    for key in ["totalCount", "total_count", "count"]:
        value = payload.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


async def _get_json(
    client: httpx.AsyncClient,
    path: str,
    *,
    params: dict[str, str],
    operation: str,
) -> dict:
    try:
        response = await client.get(f"{CLINICALTRIALS_API_BASE_URL}{path}", params=params)
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise ClinicalTrialsError(f"ClinicalTrials.gov {operation} request timed out") from exc
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code == 403 and isinstance(client, httpx.AsyncClient):
            return await asyncio.to_thread(_get_json_with_urllib, path, params, operation)
        if status_code == 403:
            raise ClinicalTrialsError(
                "ClinicalTrials.gov returned HTTP 403 Forbidden. "
                "The API may be blocking the current HTTP client, network, proxy, VPN, or IP range."
            ) from exc
        raise ClinicalTrialsError(
            f"ClinicalTrials.gov {operation} request failed with HTTP {status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise ClinicalTrialsError(f"ClinicalTrials.gov {operation} request failed") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise ClinicalTrialsError("ClinicalTrials.gov returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ClinicalTrialsError("ClinicalTrials.gov returned unexpected JSON")
    return payload



def _get_json_with_urllib(path: str, params: dict[str, str], operation: str) -> dict:
    query = urllib.parse.urlencode(params)
    url = f"{CLINICALTRIALS_API_BASE_URL}{path}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise ClinicalTrialsError(
            f"ClinicalTrials.gov {operation} request failed with HTTP {exc.code}"
        ) from exc
    except urllib.error.URLError as exc:
        raise ClinicalTrialsError(f"ClinicalTrials.gov {operation} request failed") from exc
    except TimeoutError as exc:
        raise ClinicalTrialsError(f"ClinicalTrials.gov {operation} request timed out") from exc

    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise ClinicalTrialsError("ClinicalTrials.gov returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ClinicalTrialsError("ClinicalTrials.gov returned unexpected JSON")
    return payload

def _parse_search_record(study: dict) -> TrialSearchRecord:
    protocol = study.get("protocolSection", {})
    identification = protocol.get("identificationModule", {})
    nct_id = identification.get("nctId")
    if not nct_id:
        raise ClinicalTrialsError("ClinicalTrials.gov study is missing NCT ID")

    status = protocol.get("statusModule", {})
    design = protocol.get("designModule", {})
    conditions = protocol.get("conditionsModule", {})
    arms = protocol.get("armsInterventionsModule", {})

    return TrialSearchRecord(
        nct_id=nct_id,
        brief_title=_clean_text(identification.get("briefTitle")),
        official_title=_clean_text(identification.get("officialTitle")),
        status=_clean_text(status.get("overallStatus")),
        phase=_join_values(design.get("phases")),
        study_type=_clean_text(design.get("studyType")),
        conditions=[value for value in conditions.get("conditions", []) if value],
        interventions=_parse_intervention_names(arms),
        enrollment=_parse_enrollment(design),
        start_date=_parse_date(status.get("startDateStruct")),
        completion_date=_parse_date(status.get("completionDateStruct")),
        last_update_posted=_parse_date(status.get("lastUpdatePostDateStruct")),
        clinicaltrials_url=f"https://clinicaltrials.gov/study/{nct_id}",
    )


def _parse_trial_summary(study: dict) -> TrialSummary:
    record = _parse_search_record(study)
    protocol = study.get("protocolSection", {})
    description = protocol.get("descriptionModule", {})
    arms = protocol.get("armsInterventionsModule", {})
    outcomes = protocol.get("outcomesModule", {})
    eligibility = protocol.get("eligibilityModule", {})
    locations = protocol.get("contactsLocationsModule", {})
    sponsor = protocol.get("sponsorCollaboratorsModule", {})
    references = protocol.get("referencesModule", {})

    return TrialSummary(
        **record.model_dump(mode="json"),
        brief_summary=_clean_text(description.get("briefSummary")),
        detailed_description=_clean_text(description.get("detailedDescription")),
        arms=_parse_arm_names(arms),
        primary_outcomes=_parse_outcomes(outcomes.get("primaryOutcomes", [])),
        secondary_outcomes=_parse_outcomes(outcomes.get("secondaryOutcomes", [])),
        eligibility=_clean_text(eligibility.get("eligibilityCriteria")),
        locations=_parse_locations(locations.get("locations", [])),
        sponsor=_parse_lead_sponsor(sponsor),
        collaborators=_parse_collaborators(sponsor),
        references=_parse_references(references.get("references", [])),
        result_references=_parse_references(references.get("resultReferences", [])),
    )


def _parse_intervention_names(arms: dict) -> list[str]:
    interventions = arms.get("interventions", [])
    names = []
    for intervention in interventions:
        name = _clean_text(intervention.get("name"))
        if name:
            names.append(name)
    return names


def _parse_arm_names(arms: dict) -> list[str]:
    groups = arms.get("armGroups", [])
    names = []
    for group in groups:
        label = _clean_text(group.get("label"))
        if label:
            names.append(label)
    return names


def _parse_enrollment(design: dict) -> int | None:
    enrollment = design.get("enrollmentInfo", {}).get("count")
    if isinstance(enrollment, int):
        return enrollment
    if isinstance(enrollment, str) and enrollment.isdigit():
        return int(enrollment)
    return None


def _parse_date(date_struct: dict | None) -> str | None:
    if not isinstance(date_struct, dict):
        return None
    return _clean_text(date_struct.get("date"))


def _parse_outcomes(outcomes: Iterable[dict]) -> list[TrialOutcome]:
    return [
        TrialOutcome(
            measure=_clean_text(outcome.get("measure")),
            description=_clean_text(outcome.get("description")),
            time_frame=_clean_text(outcome.get("timeFrame")),
        )
        for outcome in outcomes
    ]


def _parse_locations(locations: Iterable[dict]) -> list[str]:
    parsed = []
    for location in locations:
        parts = [
            _clean_text(location.get("facility")),
            _clean_text(location.get("city")),
            _clean_text(location.get("state")),
            _clean_text(location.get("country")),
        ]
        label = ", ".join(part for part in parts if part)
        if label:
            parsed.append(label)
    return parsed


def _parse_lead_sponsor(sponsor: dict) -> str | None:
    return _clean_text(sponsor.get("leadSponsor", {}).get("name"))


def _parse_collaborators(sponsor: dict) -> list[str]:
    collaborators = sponsor.get("collaborators", [])
    return [name for item in collaborators if (name := _clean_text(item.get("name")))]


def _parse_references(references: Iterable[dict]) -> list[TrialReference]:
    parsed = []
    for reference in references:
        pmid = _clean_text(reference.get("pmid")) or _extract_pmid(reference.get("citation"))
        parsed.append(
            TrialReference(
                citation=_clean_text(reference.get("citation")),
                pmid=pmid,
                type=_clean_text(reference.get("type")),
            )
        )
    return parsed


def _extract_pmid(citation: str | None) -> str | None:
    if not citation:
        return None
    match = re.search(r"PMID:\s*(\d+)", citation, flags=re.IGNORECASE)
    return match.group(1) if match else None


def _unique_pmids(references: Iterable[TrialReference]) -> list[str]:
    seen = set()
    pmids = []
    for reference in references:
        if reference.pmid and reference.pmid not in seen:
            seen.add(reference.pmid)
            pmids.append(reference.pmid)
    return pmids


def _join_values(values: list[str] | None) -> str | None:
    if not values:
        return None
    return ", ".join(values)
