"""PubMed API client and response normalization."""

from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from collections.abc import Iterable

import httpx

from .models import EvidenceTableRow, PubMedArticle, PubMedSearchResult

NCBI_EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DEFAULT_TIMEOUT = 20.0
MAX_RESULTS_LIMIT = 50


class PubMedError(RuntimeError):
    """Raised when PubMed cannot return a usable response."""


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(html.unescape(value).split())
    return cleaned or None


def _require_query(query: str) -> str:
    normalized = query.strip()
    if not normalized:
        raise ValueError("query must not be empty")
    return normalized


def _normalize_max_results(max_results: int) -> int:
    if max_results < 1:
        raise ValueError("max_results must be at least 1")
    return min(max_results, MAX_RESULTS_LIMIT)


async def search_pubmed(
    query: str,
    max_results: int = 10,
    year_from: int | None = None,
    year_to: int | None = None,
    article_types: list[str] | None = None,
) -> PubMedSearchResult:
    """Search PubMed and return normalized article metadata."""

    normalized_query = _build_query(
        _require_query(query),
        year_from=year_from,
        year_to=year_to,
        article_types=article_types,
    )
    retmax = _normalize_max_results(max_results)

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        pmids = await _search_pmids(client, normalized_query, retmax)
        articles = await _fetch_articles(client, pmids) if pmids else []

    return PubMedSearchResult(query=query, count=len(articles), articles=articles)


async def get_pubmed_article(pmid: str) -> PubMedArticle:
    """Fetch one PubMed article by PMID."""

    normalized_pmid = pmid.strip()
    if not normalized_pmid or not normalized_pmid.isdigit():
        raise ValueError("pmid must be a non-empty numeric string")

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        articles = await _fetch_articles(client, [normalized_pmid])

    if not articles:
        raise PubMedError(f"No PubMed article found for PMID {normalized_pmid}")
    return articles[0]


def build_evidence_table(articles: Iterable[PubMedArticle]) -> list[EvidenceTableRow]:
    """Build a compact evidence table from normalized PubMed articles."""

    return [
        EvidenceTableRow(
            pmid=article.pmid,
            year=article.year,
            title=article.title,
            journal=article.journal,
            article_types=article.article_types,
            doi=article.doi,
            pubmed_url=article.pubmed_url,
        )
        for article in articles
    ]


def _build_query(
    query: str,
    *,
    year_from: int | None,
    year_to: int | None,
    article_types: list[str] | None,
) -> str:
    parts = [query]
    if year_from is not None or year_to is not None:
        start = year_from if year_from is not None else 1800
        end = year_to if year_to is not None else 3000
        if start > end:
            raise ValueError("year_from must be less than or equal to year_to")
        parts.append(f'("{start}"[Date - Publication] : "{end}"[Date - Publication])')
    if article_types:
        type_query = " OR ".join(
            f'"{article_type}"[Publication Type]' for article_type in article_types
        )
        parts.append(f"({type_query})")
    return " AND ".join(parts)


async def _search_pmids(client: httpx.AsyncClient, query: str, max_results: int) -> list[str]:
    try:
        response = await client.get(
            f"{NCBI_EUTILS_BASE_URL}/esearch.fcgi",
            params={
                "db": "pubmed",
                "term": query,
                "retmode": "json",
                "retmax": str(max_results),
                "sort": "relevance",
            },
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise PubMedError("PubMed search request timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise PubMedError(
            f"PubMed search request failed with HTTP {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise PubMedError("PubMed search request failed") from exc

    payload = response.json()
    return payload.get("esearchresult", {}).get("idlist", [])


async def _fetch_articles(client: httpx.AsyncClient, pmids: list[str]) -> list[PubMedArticle]:
    if not pmids:
        return []

    try:
        response = await client.get(
            f"{NCBI_EUTILS_BASE_URL}/efetch.fcgi",
            params={
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "xml",
            },
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise PubMedError("PubMed fetch request timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise PubMedError(
            f"PubMed fetch request failed with HTTP {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise PubMedError("PubMed fetch request failed") from exc

    return _parse_pubmed_xml(response.text)


def _parse_pubmed_xml(xml_text: str) -> list[PubMedArticle]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise PubMedError("PubMed returned invalid XML") from exc

    articles: list[PubMedArticle] = []
    for article_node in root.findall(".//PubmedArticle"):
        medline = article_node.find("MedlineCitation")
        article = article_node.find("MedlineCitation/Article")
        if medline is None or article is None:
            continue

        pmid = _clean_text(medline.findtext("PMID"))
        title = _clean_text(article.findtext("ArticleTitle"))
        if not pmid or not title:
            continue

        authors = _parse_authors(article)
        journal = _clean_text(article.findtext("Journal/Title"))
        publication_date = _parse_publication_date(article)
        year = _parse_year(article, publication_date)
        article_types = [
            text
            for text in (
                _clean_text(node.text)
                for node in article.findall("PublicationTypeList/PublicationType")
            )
            if text
        ]
        abstract = _parse_abstract(article)
        doi = _parse_doi(article_node)

        articles.append(
            PubMedArticle(
                pmid=pmid,
                title=title,
                authors=authors,
                journal=journal,
                year=year,
                publication_date=publication_date,
                article_types=article_types,
                doi=doi,
                abstract=abstract,
                pubmed_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            )
        )

    return articles


def _parse_authors(article: ET.Element) -> list[str]:
    authors: list[str] = []
    for author in article.findall("AuthorList/Author"):
        collective_name = _clean_text(author.findtext("CollectiveName"))
        if collective_name:
            authors.append(collective_name)
            continue
        last_name = _clean_text(author.findtext("LastName"))
        fore_name = _clean_text(author.findtext("ForeName"))
        if last_name and fore_name:
            authors.append(f"{fore_name} {last_name}")
        elif last_name:
            authors.append(last_name)
    return authors


def _parse_publication_date(article: ET.Element) -> str | None:
    date_node = article.find("Journal/JournalIssue/PubDate")
    if date_node is None:
        return None
    year = _clean_text(date_node.findtext("Year"))
    month = _clean_text(date_node.findtext("Month"))
    day = _clean_text(date_node.findtext("Day"))
    medline_date = _clean_text(date_node.findtext("MedlineDate"))
    if year:
        return " ".join(part for part in [year, month, day] if part)
    return medline_date


def _parse_year(article: ET.Element, publication_date: str | None) -> int | None:
    year_text = _clean_text(article.findtext("Journal/JournalIssue/PubDate/Year"))
    if year_text and year_text.isdigit():
        return int(year_text)
    if publication_date:
        for token in publication_date.replace("-", " ").split():
            if token.isdigit() and len(token) == 4:
                return int(token)
    return None


def _parse_abstract(article: ET.Element) -> str | None:
    parts: list[str] = []
    for abstract_text in article.findall("Abstract/AbstractText"):
        label = abstract_text.attrib.get("Label")
        text = _clean_text("".join(abstract_text.itertext()))
        if not text:
            continue
        parts.append(f"{label}: {text}" if label else text)
    return "\n".join(parts) if parts else None


def _parse_doi(article_node: ET.Element) -> str | None:
    for node in article_node.findall(".//ArticleIdList/ArticleId"):
        if node.attrib.get("IdType") == "doi":
            return _clean_text(node.text)
    for node in article_node.findall(".//ELocationID"):
        if node.attrib.get("EIdType") == "doi":
            return _clean_text(node.text)
    return None
