# LUNDUS Business Engine — P1 Integration Layer

Status: DEVELOPMENT / NON-PRODUCTION

## Purpose

P1 connects the Business Engine platform foundation to existing LD specialist systems without creating duplicate generic engines.

The P1 rule is:

**Tenant Context → Entitlement → Verified Membership → Existing Source of Truth → Read/Bounded Workflow → Existing Human Gates**

## Reused specialist systems

P1 registers bindings to:

- LD Client Portal / Customer Control Center;
- LD Ready Business Delivery Factory;
- LD Pricing & Estimation Intelligence;
- LD Project Profitability & Capacity;
- LD Executive Commercial Mission Control.

These modules remain the owners of their own domain logic and evidence.

## What P1 does

P1:

- verifies the P0 tenant/runtime contract;
- requires verified organisation-membership evidence;
- verifies that the selected Industry Pack contains required capabilities;
- returns deterministic source/contract bindings;
- records that the action is REUSE rather than BUILD_NEW;
- keeps Production and live charging locked;
- routes material commercial/Production actions to existing human gates.

## What P1 does not do

P1 does not:

- create a second customer portal;
- create another CRM, quotation, payment or accounting engine;
- calculate a replacement price or margin model;
- create another Mission Control;
- infer payment, QA, UAT, delivery or Production truth;
- publish customer prices;
- charge customers;
- deploy Production;
- widen privileges.

## Authority invariant

An integration is not authority.

A surface may expose read-only or bounded workflow capability, but the integration layer cannot elevate that surface into Production, charging, pricing or privilege authority.

Human-only actions remain HUMAN_GATE.

## Source-of-truth integrity

Regression tests verify that registered source and contract artifacts exist and that external commercial contracts continue to declare Production activation as unauthorized.

If a source disappears, a capability is missing, membership is unverified, or a new surface is not registered, the integration fails closed.
