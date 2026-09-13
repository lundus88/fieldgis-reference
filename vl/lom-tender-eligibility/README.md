# LOM P6.8 Tender Eligibility & Service-Code Registry

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: match Sabah survey tender requirements against evidence-backed firm eligibility and service codes without widening commercial authority.

## Decision classes

- `DIRECT_MATCH` — tender scope is confirmed and all supplied mandatory licence/discipline/procurement-code evidence is current and matched.
- `CONDITIONAL_MATCH` — technical fit exists but scope or mandatory procurement evidence remains unconfirmed. This is not authority to bid.
- `PARTNER_MATCH` — a current firm has partial technical fit but lacks one or more confirmed mandatory codes; partnership may be investigated by a human.
- `HOLD` — current licence authority is expired, stale, restricted from new work, or other mandatory evidence fails closed.

## Evidence rules

1. Keyword matches produce candidate service codes only; they never confirm tender scope.
2. Expired/stale licences fail closed.
3. A licence restricted to outstanding work cannot qualify the firm for a new tender.
4. Missing PUKONSA/MOF evidence is never inferred from technical capability.
5. Project experience strengthens relevance but never substitutes for a mandatory registration or licence.
6. No personal identity numbers, home addresses, or private contact details from source profiles are stored here.

## Governance

This module is recommendation-only. Customer outreach, bid submission, quotation, pricing, contracting, financial commitments, production mutation, authority changes and protected-main merge remain HUMAN_ONLY.
