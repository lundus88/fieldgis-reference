# LOM Knowledge Foundation P0

Status: NON-PRODUCTION / GOVERNANCE FOUNDATION

Owner: **LOM Knowledge Librarian**

Purpose: provide one authoritative knowledge control plane for domain/jurisdiction-aware retrieval without creating a second memory or document store.

## Rules

- Existing storage remains the source location; this registry stores metadata, provenance and authority.
- Authoritative/official sources outrank professional and technical references when current and applicable to the jurisdiction.
- Stale, superseded, conflicting or low-confidence material fails closed for consequential decisions.
- Duplicates are detected and flagged; they are never deleted automatically.
- Retrieval consumers must filter by domain + jurisdiction + status before semantic similarity.
- Source conflicts must be surfaced with provenance and authority reasoning.

## Required metadata

name, domain, jurisdiction, source, provenance, authority_level, version_or_date, status, superseded_by, confidence, tags, location.

## Integration target

`LOM Memory -> Knowledge Registry -> Retrieval Policy -> Orchestrator -> Specialist/Worker`

This package is additive. It does not replace Project State Truth, the evidence ledger, file storage, or application databases.
