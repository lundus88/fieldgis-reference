# LD Change Request & Scope Ledger v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: protect both customer expectations and LD margin after scope approval.

## Core rule

Approved scope is immutable. Material changes require a Change Request before they enter BUILDING.

## Flow

REQUESTED
→ IMPACT REVIEW
→ CUSTOMER DECISION
→ HUMAN COMMERCIAL APPROVAL
→ APPROVED
→ NEW SCOPE VERSION
→ APPLIED

## Impact review

Every material change must identify:
- scope impact
- cost impact
- time impact
- dependency impact
- risk impact

The customer sees impact before approval.

## Important fairness rule

The following are not automatically billable Change Requests:
- work already included in the approved scope;
- defects against agreed acceptance criteria;
- internal AI/build failures;
- regression remediation;
- LD/VL implementation mistakes.

These remain governed by the original commercial agreement and applicable support/remediation rules.

## Audit

The original approved scope is never overwritten. An approved Change Request creates a new version while retaining the prior scope snapshot and decision evidence.

No Production or commercial activation is authorized by this package.
