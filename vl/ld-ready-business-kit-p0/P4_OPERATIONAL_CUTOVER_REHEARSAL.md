# LD Ready Business Kit P4 — Operational Cutover Rehearsal

Status: PRE-ACTIVATION / NON-PRODUCTION  
Tracking: Issue #381

## Objective

Complete the operational work that can be proven before the official LD business phone and company account are ready.

P4 is a rehearsal layer, not an activation layer.

## Current external gates

- dedicated LD business phone: IN_PROGRESS
- company account: IN_PROGRESS

Neither may be inferred PASS from an application receipt, screenshot, pending registration or provider acknowledgement. Independent evidence is required.

## Customer-zero rehearsal

Customer Zero is synthetic. It rehearses:
- preflight evaluation;
- evidence-pack shape;
- kill-switch decisions;
- rollback contract;
- incident escalation;
- stop-at-human-gate behaviour.

It performs:
- zero real payments;
- zero Production mutations;
- zero real customer commitments;
- zero public launch actions.

## Kill-switch matrix

Operational controls are intentionally separable:
- lead intake can be disabled without removing the informational site;
- checkout can be disabled without deleting commercial information;
- billing can be disabled independently of static/support surfaces;
- outbound notification can be paused without changing authoritative payment/order state.

The exact implementation/fingerprint must be verified in the target Production environment later. P4 does not assume an environment variable name that has not been evidenced.

## Rollback contract

A live rollback proof later requires:
- immutable candidate deployment reference;
- distinct known-good deployment reference;
- lead-intake disable evidence;
- checkout disable evidence;
- billing disable evidence;
- incident path evidence;
- rollback procedure/drill evidence.

Documentation alone is not a live rollback drill.

## Incident bridge

If money/payment state is uncertain:
1. stop new checkout/billing;
2. preserve evidence;
3. hold fulfilment;
4. reconcile provider and backend state;
5. escalate to a human financial owner.

If public intake is abused:
1. disable intake;
2. preserve informational/support surface;
3. retain audit evidence;
4. investigate before re-enabling.

If a deployment is unhealthy:
1. stop activation;
2. identify candidate and known-good artifacts;
3. use the approved rollback path;
4. verify health after rollback;
5. link incident evidence.

## Future live evidence

Use p4-future-live-evidence-pack.json only as an empty template until attributable evidence exists.

No placeholder or synthetic reference can be treated as live certification evidence.

## Authority boundary

Even a complete future evidence pack only allows assessment for a bounded controlled certification.

It does not itself authorize:
- Production deploy;
- customer charging;
- public launch;
- DNS mutation;
- protected-main merge.

Those remain separate human gates.

## Exit criterion

P4 engineering is complete when CI proves:
- current external states remain HOLD;
- Customer Zero remains synthetic;
- kill switches are logically independent;
- incomplete rollback evidence fails closed;
- a known-good target must differ from the candidate;
- a full simulated fixture reaches only bounded-certification readiness, never public-launch authority.
