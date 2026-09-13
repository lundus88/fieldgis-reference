# LOM P6.4 Director Pursuit Queue

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: transform evidence-bound P6.3 pursuit evaluations into a short Director-facing priority queue without expanding authority.

Output per item:
- queue_rank
- pursuit_decision
- director_action
- reason
- next_best_action
- urgency_score
- evidence_gap_count

Governance:
- upstream pursuit decision is preserved;
- HOLD cannot be promoted by urgency;
- WATCHLIST is monitor-only;
- CONTINUE means ready for human pursuit review, not autonomous execution;
- deadline urgency is used only when supplied as evidence;
- unknown critical evidence remains fail-closed;
- outreach, bid, quotation, pricing, contracting, production actions and protected-main merges remain HUMAN_ONLY.
