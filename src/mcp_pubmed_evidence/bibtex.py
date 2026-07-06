"""BibTeX export helpers for PubMed articles."""

from __future__ import annotations

import re

from .models import PubMedArticle


def article_to_bibtex(article: PubMedArticle) -> str:
    """Convert one normalized PubMed article to a BibTeX @article entry."""

    key = _citation_key(article)
    fields: list[tuple[str, str | None]] = [
        ("title", article.title),
        ("author", " and ".join(article.authors) if article.authors else None),
        ("journal", article.journal),
        ("year", str(article.year) if article.year else None),
        ("doi", article.doi),
        ("pmid", article.pmid),
        ("url", str(article.pubmed_url)),
    ]
    rendered_fields = [f"  {name} = {{{_escape_bibtex(value)}}}" for name, value in fields if value]
    return "@article{" + key + ",\n" + ",\n".join(rendered_fields) + "\n}"


def articles_to_bibtex(articles: list[PubMedArticle]) -> str:
    """Convert a list of normalized PubMed articles to BibTeX entries."""

    return "\n\n".join(article_to_bibtex(article) for article in articles)


def _citation_key(article: PubMedArticle) -> str:
    first_author = "pubmed"
    if article.authors:
        first_author = article.authors[0].split()[-1].lower()
    year = article.year or "nd"
    title_word = "article"
    for token in re.findall(r"[A-Za-z0-9]+", article.title.lower()):
        if len(token) > 3:
            title_word = token
            break
    return f"{_slug(first_author)}{year}{_slug(title_word)}{article.pmid}"


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "", value)
    return slug or "pubmed"


def _escape_bibtex(value: str) -> str:
    return value.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
