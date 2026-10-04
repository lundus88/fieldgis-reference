# LOM P0-B — Context Engineering & Provenance-Preserving Compaction

Status: DEVELOPMENT / NON-PRODUCTION

## Design decision

The existing Context Governance layer remains canonical for allow/deny decisions.

Compaction occurs **only after** governance has removed denied resources. P0-B does not widen the allowed context set and cannot re-introduce denied material.

## P0 method

P0 uses deterministic **extractive** compaction:

1. validate the governed/allowed resources;
2. preserve the full-source SHA-256 for each allowed resource;
3. split large sources into bounded excerpts;
4. score excerpts using task-term overlap;
5. keep at least one excerpt from every allowed resource;
6. fill remaining budget with the most task-relevant excerpts;
7. preserve source line spans plus source/excerpt hashes;
8. fail closed when the budget is too small to preserve governed resource coverage.

No abstractive/model-generated summary is permitted in P0.

## Why extractive first

A generated summary can silently:
- omit a safety invariant;
- weaken an authority boundary;
- alter a factual statement;
- detach a statement from provenance.

P0 therefore optimizes context size without manufacturing replacement facts.

## Canonical boundary

Context Policy
→ allow/deny
→ governed context
→ extractive compaction
→ provenance manifest
→ pre-model invocation

Denied content never reaches the compactor.

## Authority

- autonomous ceiling: PREPARE_PR
- Production authority: HUMAN_ONLY
- protected-main merge: HUMAN_ONLY
- execution authority: NONE
- source truth preserved: REQUIRED
- abstractive summary generation: FORBIDDEN in P0

## Future extension

A later phase may admit independently validated semantic summaries, but only as derived context with immutable links to original source spans and evidence. Original evidence must remain authoritative.
