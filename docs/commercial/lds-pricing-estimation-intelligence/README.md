# LD Pricing & Estimation Intelligence v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: provide evidence-backed internal pricing guidance before a human-approved quotation is issued.

## Position in the commercial flow

System Blueprint
→ Cost Evidence
→ Pricing Intelligence
→ Human Commercial Review
→ Quotation

## Important distinction

VL Factory Credit is an execution/resource estimate. It is not a Ringgit price and must not be converted directly into the customer amount.

## Inputs

- approved scope snapshot
- estimated delivery cost
- comparable historical projects
- rework rate
- support burden
- third-party cost
- risk contingency
- target margin policy
- capacity pressure

## Output

The engine returns an internal price range plus evidence confidence:
- HIGH
- MEDIUM
- LOW

LOW confidence or stale/incomplete evidence does not produce a quote-ready recommendation.

## Human authority

This component cannot:
- issue a quotation;
- change an approved quotation;
- publish pricing;
- activate an offer;
- charge a customer.

The final customer amount remains a separate human-approved commercial decision.
