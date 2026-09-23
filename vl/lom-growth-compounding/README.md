# LOM Growth & Compounding Control Layer — P0

Status: DEVELOPMENT / NON-PRODUCTION

## Purpose

Convert proven high-growth AI operating patterns into a governed, measurable LOM improvement loop without creating a second authority, self-improvement, telemetry, evidence, approval, or deployment system.

The layer answers one bounded question:

> Given current evidence, which reversible non-Production improvement should LOM test next to improve Speed, Automation, Distribution, Learning, or Compounding?

It does not execute the change. It produces an evidence-bound improvement candidate that can be handed to the existing CAIE pipeline.

## Operating doctrine

LOM applies this sequence:

1. Define the economic/user outcome.
2. Question the requirement.
3. Delete unnecessary steps.
4. Simplify the remaining path.
5. Build the minimum working system.
6. Test with deterministic evidence.
7. Measure real outcome.
8. Find the current bottleneck.
9. Accelerate only the bottleneck.
10. Automate only after the process is understood.
11. Observe the result.
12. Learn and repeat.

This composes the already-approved first-principles doctrine with five growth levers:

- **Speed** — reduce time-to-value and cycle time without weakening QA/evidence.
- **Automation** — increase automation only for already automation-eligible work.
- **Distribution** — improve qualified acquisition and conversion with evidence, never fabricated demand.
- **Learning** — shorten evidence-to-improvement latency and close feedback loops.
- **Compounding** — favor improvements that increase repeat/referral, reuse, retention, reusable capability, or lower marginal effort.

## Non-goals

This package MUST NOT:

- merge protected main;
- deploy/release/promote/rollback Production;
- mutate Production data;
- widen authority;
- self-approve;
- remove mandatory human gates;
- create pricing, legal, bid, contract, financial, or customer commitments;
- infer demand, ROI, revenue, retention, safety, or eligibility from missing evidence;
- replace CAIE, Mission Control, System Health/Drift, Evidence Ledger, Project State Truth, Learning/Evaluation, or the existing anti-bottleneck guard.

## Evidence contract

A recommendation is eligible only when:

- the evidence reference is present and externally addressable;
- evidence is fresh;
- metric values are finite and non-negative;
- the target is non-Production, reversible, and automation-eligible where automation is proposed;
- no critical incident, unresolved evidence gap, or mandatory human approval is bypassed.

Missing, stale, contradictory, malformed, or non-finite evidence => `HOLD`.

## Output contract

The evaluator emits one of:

- `NO_ACTION` — evidence is healthy; no bounded improvement is justified;
- `CANDIDATE` — prepare a reversible non-Production improvement candidate for CAIE;
- `HOLD` — evidence or policy is insufficient;
- `HUMAN_REVIEW` — the detected bottleneck touches a mandatory human boundary or consequential authority.

Every `CANDIDATE` includes:

- lever;
- bottleneck reason;
- bounded target;
- recommended experiment;
- success metric;
- rollback requirement;
- evidence reference;
- CAIE-compatible target class.

## Authority invariants

- autonomous ceiling: `PREPARE_PR`
- protected-main merge: `HUMAN_ONLY`
- Production authority: `HUMAN_ONLY`
- financial/customer/legal/pricing commitments: `HUMAN_ONLY`
- self-approval: `FORBIDDEN`
- automatic gate removal: `FORBIDDEN`
- execution authority: `NONE`

## Design principle

LOM does not optimize everything simultaneously. It identifies the highest-evidence current bottleneck, proposes one bounded experiment, validates it, then learns before proposing the next one. This prevents feature accumulation and keeps optimization focused on throughput and user value rather than activity volume.
