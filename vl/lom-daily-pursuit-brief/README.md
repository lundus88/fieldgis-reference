# LOM Daily Pursuit Brief

P6.5 renders the P6.4 Director Pursuit Queue into a compact management-by-exception section for the daily LOM Director Brief.

Rules:
- report-only; no consequential writes
- preserve upstream CONTINUE / HOLD / WATCHLIST decisions
- detail only the highest-priority Director-attention items
- summarize monitor-only items as a count
- expose one next-best-action per detailed item
- missing or invalid queue input fails closed as EVIDENCE_UNAVAILABLE
- protected-main merge, production actions, customer outreach, bid/quote submission, pricing, contracting and financial commitments remain HUMAN_ONLY
