# LD Customer Disappointment Prevention v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: detect customer disappointment risk before it becomes a complaint, refund dispute, churn, or reputational damage.

## Core principle

Do not wait for the customer to complain.

The system should observe delivery, support, scope, dependency, payment, security and adoption signals and raise an early warning when the customer experience is likely to deteriorate.

## Severity

- P0 — trust/data/money/security failure. Immediate human escalation.
- P1 — material delivery/support/expectation risk. Same-business-day mitigation plan.
- P2 — frustration risk. Proactive communication/workflow correction.
- P3 — minor/cosmetic issue. Track.

## Required customer experience controls

1. Expectation control before payment.
2. First visible value for eligible work within 48-72 hours.
3. No silent blockers.
4. Client-action-required state for missing customer dependencies.
5. Transparent ETA rebaseline.
6. Formal change control for scope creep.
7. UAT evidence before acceptance.
8. Warranty/support path for defects.
9. Clear escalation for payment/refund/security/data incidents.
10. Online-only support must still feel responsive through prompt acknowledgement, clear ownership and written status.

## Communication rules

- Never say "on track" if evidence shows a blocker.
- Never hide a dependency or rebaseline.
- State what happened, current impact, customer action if any, mitigation, and next checkpoint.
- Avoid unnecessary meetings; standard communication remains asynchronous/text-first.
- P0 financial/security/data matters require human review before consequential commitments.

## Integration points

This layer complements rather than duplicates:
- Fast Delivery System
- Statement of Work / acceptance criteria
- Refund & Cancellation policy
- Commercial support/rollback runbook
- payment/order evidence
- UAT and delivery acceptance

## Client status model

CLEAR
WATCH
AT_RISK
CLIENT_ACTION_REQUIRED
BLOCKED
RECOVERY
CLOSED

A project may be technically healthy but customer-experience AT_RISK if communication or expectation controls are failing.

## Evidence rule

Every active P0/P1/P2 risk should carry evidence refs. If a risk is asserted without evidence, the automation must HOLD rather than invent a diagnosis.
