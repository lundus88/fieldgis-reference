# LOM 2.0 Gate F — Director Mission Control

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: provide a single director-facing control surface for objective intake, lifecycle visibility, evidence maturity, agent status, exception routing and outcome reporting.

Invariants:
- report/advisory only;
- no protected-main merge automation;
- no production deployment/release authority;
- no production data mutation;
- no authority widening;
- no customer outreach, bid, quotation, contract or financial commitment;
- unknown authority => HOLD;
- missing evidence => HOLD/REVIEW;
- consequential actions => HUMAN_ONLY escalation.

Mission Control composes Gate E lifecycle state into a director snapshot. It may recommend next actions but cannot execute consequential actions.
