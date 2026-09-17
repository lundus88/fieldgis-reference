# LOM P3 Live Portfolio Runtime

Status: DEVELOPMENT / NON-PRODUCTION
Tracking: Issue #162

Purpose: establish a read-only, evidence-backed portfolio runtime for Lundus projects and bind that portfolio into canonical LOM 6.10 Project State Truth for Director Mission Control.

Core runtime flow:
observe -> normalize -> assess -> ledger-bind evidence -> derive Project State Truth -> bind Director Mission Control -> stop at human decision where required.

## Canonical portfolio catalog

`source-registry.json` is the single project catalog used by this runtime. Do not create a second project list for Mission Control.

Registered repository-backed projects are READ_ONLY. A known project without a verifiable authoritative repository may be declared `UNREGISTERED_HOLD`; it must not be assigned an invented repository or positive readiness state.

Current catalog includes VL/VRS Labs, e-BKL, SabahLot, Spatial & Land Planner (SLP), LundusLead, UrusMY and KontenStudio. SLP is explicitly fail-closed until an authoritative source is registered.

## Project State Truth bridge

`portfolio_truth_bridge.py` converts source observations into the existing append-only operational ledger and canonical LOM 6.10 Project State Truth. Repository activity by itself can establish only `UNVERIFIED` presence or a fail-closed `HOLD`; it cannot self-promote a project to `VERIFIED`, `APPROVED` or `RELEASED`.

The bridge then calls the existing truth-bound Director Mission Control path. It does not create a second dashboard, evidence registry, ledger or execution runtime.

## Safety invariants

- source repositories are observed read-only;
- no production deployment or data mutation;
- no positive state without evidence;
- repository activity alone never means production readiness;
- stale, inaccessible, empty, missing or unregistered sources fail closed;
- SLP has no invented repository binding;
- autonomous ceiling remains `PREPARE_PR`;
- execution authority remains `NONE`;
- control execution remains `DISABLED`;
- protected-main merge remains `HUMAN_ONLY`;
- Production authority remains `HUMAN_ONLY`.
