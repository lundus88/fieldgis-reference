# LOM P6.8.1 Tender Watch & Client Need Watch

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: detect and classify opportunities where a tender, quotation, project or client needs land surveying, mapping or related geospatial services. This module does **not** rank, select or compare survey firms.

## Canonical engine

`opportunity_watch.py` is the canonical operational matcher. The older `match_tender.py` is legacy P6.8 code and must not be used by automation for firm ranking or firm-selection decisions.

## Operational focus

1. Tender Watch — detect tenders, quotations, RFQs and RFPs with explicit or possible survey/mapping/geospatial scope.
2. Client Need Watch — detect contractors, developers, consultants, landowners, agencies or project teams that explicitly need or may need survey/mapping/geospatial services.
3. Service-Code Match — map wording to candidate Sabah Surveyors Board discipline codes and known survey/mapping procurement service codes.
4. Evidence-bound classification — keyword matches are discovery signals only; ambiguous scope remains potential until verified from source documents.

## Opportunity classes

- `DIRECT_TENDER` — a tender/quotation/RFQ/RFP explicitly confirms survey, mapping or geospatial scope.
- `CONFIRMED_CLIENT_NEED` — a non-tender client/project source explicitly confirms a need for survey, mapping or geospatial services.
- `POTENTIAL_SERVICE_NEED` — service signals exist, but the actual survey/mapping scope is not yet confirmed.
- `NO_RELEVANT_SIGNAL` — no supported survey/mapping/geospatial service signal was detected.

## Service families monitored

Cadastral and land survey, boundary/re-establishment, subdivision/strata, land acquisition, topographical survey, engineering/site survey, setting-out, as-built, GNSS/control survey, road/railway/pipeline survey, drainage/waterways, transmission line, hydrographic, aerial/drone/LiDAR, GIS/mapping and underground utility mapping.

## Firm profiles

Uploaded company profiles are retained only as evidence sources that helped establish service vocabulary and service-code references. They are **not** used by the operational matcher to decide which firm is more eligible or preferred.

## Evidence rules

1. Keywords produce candidate services/codes only; they never prove tender scope.
2. `scope_confirmed=true` must come from explicit source evidence, not inference.
3. A construction or infrastructure project may be a `POTENTIAL_SERVICE_NEED` even when survey work is plausible; it must not be promoted to a direct opportunity without explicit scope evidence.
4. Procurement-code references are captured as signals; this module does not use them to rank firms.
5. No customer outreach, bid submission, quotation, pricing or contracting is automated.

## Governance

This module is read/recommendation-only. Customer outreach, bid submission, quotation, pricing, contracting, financial commitments, production mutation, authority changes and protected-main merge remain HUMAN_ONLY.
