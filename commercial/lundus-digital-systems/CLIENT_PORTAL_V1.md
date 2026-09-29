# LD Client Portal / Customer Control Center v1

Status: DEVELOPMENT / NON-PRODUCTION
Mode: READ-ONLY COMPOSITION

Purpose: give LD customers one place to understand the commercial and delivery state of their project without creating a second source of truth.

## What the customer sees

- project status
- next action
- quotation
- invoice
- payment status
- receipt
- scope state
- milestone funding
- build status
- QA
- UAT
- delivery
- latest verified update
- support summary

## Authority model

The portal composes existing authoritative evidence. It does not write project truth.

Examples:
- PAID requires verified payment/provider evidence.
- QA PASS requires QA evidence.
- UAT ACCEPTED requires customer acceptance evidence.
- DELIVERY requires delivery evidence.
- factory SUCCEEDED/CERTIFIED does not prove Production deployment.

Unknown, stale or contradictory evidence renders REVIEW/HOLD rather than optimistic completion.

## Customer isolation

The eventual runtime must enforce authenticated customer-account/project ownership or membership before any commercial, document, support or project data is returned.

## Future actions

Request Change, UAT Approval and other mutations are visible only as disabled placeholders in v1. Each must be implemented later as a separately approved, evidence-backed, idempotent workflow.

No Production activation is authorized by this package.

## P2 backend action gateway

A non-Production Customer Action Gateway now prepares governed handoffs for:

- Request Change → existing Change Request & Scope Ledger;
- UAT Accept → existing Integrated Customer Lifecycle Gate.

This does **not** activate the portal buttons. The v1 portal remains read-only until a separate runtime activation is reviewed and approved.

The gateway reuses Customer Organization & IAM, requires idempotency, fails closed across organizations, and never mutates authoritative state itself.
