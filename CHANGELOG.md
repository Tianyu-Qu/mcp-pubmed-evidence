# Changelog

## v0.5.1 - Maintenance

### Added

- GitHub Actions CI for `ruff check .` and `pytest` on Python 3.10, 3.11, and 3.12.
- Tag version-check workflow to verify that pushed tags match `pyproject.toml`.
- Version helper scripts in `tools/`.
- Release checklist in `docs/RELEASE_CHECKLIST.md`.
- GitHub issue templates for bugs, feature requests, and maintenance tasks.

### Changed

- Updated the package version to `0.5.1`.

## v0.2.0 - ClinicalTrials.gov Evidence Tools

### Added

- ClinicalTrials.gov search via `search_trials`.
- Detailed trial summary retrieval via `get_trial_summary`.
- NCT ID to PubMed publication mapping via `map_trial_to_publications`.
- Trial schemas for compact search records, detailed summaries, outcomes, references, and publication maps.
- Local ClinicalTrials.gov demo script and sample trial output.

### Notes

This release expands the project from PubMed literature retrieval to trial registry evidence retrieval. Trial outputs are structured for research support and evidence organization, not clinical decision-making.


## v0.1.0 - PubMed MCP Server

Initial public release of `mcp-pubmed-evidence`.

### Added

- PubMed search via NCBI E-utilities using `search_pubmed`.
- Article metadata retrieval via `get_pubmed_article`.
- Abstract retrieval with provenance via `get_abstract`.
- BibTeX export via `export_bibtex`.
- Metadata-oriented evidence table generation via `build_evidence_table`.
- Pydantic schemas for stable, structured article and evidence-row outputs.
- Error handling for PubMed timeouts, HTTP errors, invalid XML, invalid PMIDs, empty queries, and missing optional metadata.
- Local demo scripts and MCP stdio smoke test.
- Cursor MCP client verification screenshots.
- Safety scope and limitations documentation for biomedical research use.

### Notes

This release is intended for biomedical literature retrieval and citation organization. It does not provide diagnosis, treatment recommendations, study-quality judgment, or medical advice.
