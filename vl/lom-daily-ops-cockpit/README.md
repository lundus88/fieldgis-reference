# LOM Daily Operations Cockpit

Status: DEVELOPMENT / NON-PRODUCTION

The cockpit turns LOM portfolio observations into one bounded operating view with:
- portfolio watch
- freshness status
- improvement queue
- exception queue
- ranked next-best-action
- explicit authority class

## Authority model
The cockpit is advisory/read-only. It may classify, rank, recommend and prepare bounded non-production improvement work. It may not merge protected main, deploy Production, mutate Production data, widen authority, change critical auth/security policy, delete protected data, submit bids, make customer/pricing/contract/financial commitments, or self-approve.

## Action classes
- AUTO_PREPARE: low/medium-risk reversible non-production improvement that may be prepared for PR.
- HUMAN_REVIEW: evidence is adequate but a consequential or high-risk boundary is involved.
- HOLD: evidence is incomplete/stale, physical verification is missing, or the target is unknown/irreversible.
- MONITOR: no current blocker; continue evidence refresh.

Maximum autonomous disposition remains PREPARE_PR.
