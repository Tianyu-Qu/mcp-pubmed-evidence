# Changelog

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
