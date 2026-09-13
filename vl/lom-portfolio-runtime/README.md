# LOM P3 Live Portfolio Runtime

Status: DEVELOPMENT / NON-PRODUCTION
Tracking: Issue #162

Purpose: establish a read-only, evidence-backed portfolio runtime for Lundus projects.

Core runtime flow:
observe -> normalize -> assess -> derive state -> generate exceptions -> generate executive snapshot -> stop at human decision where required.

Safety invariants:
- source repositories are observed read-only;
- no production deployment or data mutation;
- no positive state without evidence;
- inaccessible or empty source fails closed;
- protected-main merge remains human-gated;
- production status is never inferred from repository activity alone.
