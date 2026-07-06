# mcp-pubmed-evidence

MCP server for reliable PubMed literature retrieval, BibTeX export, and evidence table generation for biomedical research agents.

This project exposes PubMed as structured MCP tools so AI assistants can retrieve biomedical literature with source URLs, PMID/DOI metadata, article types, and citation-ready outputs instead of relying on model memory.

## Status

Early development. The first version focuses on PubMed metadata retrieval and citation provenance.

## Features

- Search PubMed with optional year and publication type filters
- Fetch normalized metadata for a PubMed article by PMID
- Export PubMed records as BibTeX entries
- Build compact evidence tables for agent workflows
- Return structured fields such as PMID, title, authors, journal, year, DOI, abstract, article types, and PubMed URL

## Safety scope

This server is intended for biomedical research support, literature discovery, citation management, and evidence organization. It is not intended for diagnosis, treatment recommendations, or medical advice.

## Installation

```powershell
git clone https://github.com/Tianyu-Qu/mcp-pubmed-evidence.git
cd mcp-pubmed-evidence
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

## MCP configuration

Example stdio configuration:

```json
{
  "mcpServers": {
    "pubmed-evidence": {
      "command": "python",
      "args": ["-m", "mcp_pubmed_evidence.server"]
    }
  }
}
```

## Tools

### `search_pubmed`

Search PubMed and return normalized article metadata.

Inputs:

- `query`: PubMed search query
- `max_results`: maximum number of articles to return, capped at 50
- `year_from`: optional publication year lower bound
- `year_to`: optional publication year upper bound
- `article_types`: optional publication type filters, such as `Review` or `Randomized Controlled Trial`

### `get_pubmed_article`

Fetch one PubMed article by PMID.

### `export_bibtex`

Fetch PubMed articles by PMID and export BibTeX entries.

### `build_evidence_table`

Fetch PubMed articles by PMID and return compact evidence table rows.

## Development

Run tests:

```powershell
pytest
```

Run linting:

```powershell
ruff check .
```

## Roadmap

- Add ClinicalTrials.gov tools
- Add OpenAlex/Crossref DOI resolution
- Add richer evidence table extraction
- Add example MCP client configurations
- Add local PDF library support
