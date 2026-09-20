# LD Project Profitability & Capacity Engine v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: help LD understand whether a project is economically healthy and whether the delivery system has capacity before making new scheduling commitments.

## Project economics

The engine separates:
- approved revenue
- payment/provider fees
- hosting/storage
- AI/API/model usage
- third-party software
- VL/factory runtime
- human delivery effort
- support burden
- rework
- refunds/credits

Contribution margin is an internal planning metric only. It is not the customer invoice amount.

## Capacity

Capacity review includes:
- active projects
- concurrent builds
- support load
- critical incidents
- available delivery capacity
- reserved capacity
- resource pressure

Critical incidents and support obligations reserve capacity before new discretionary work.

## Human authority

The engine does not:
- automatically raise prices;
- reject customers;
- cancel existing commitments;
- alter approved quotations.

AT_RISK/REVIEW/HOLD_CAPACITY results route to human commercial review for rescope, repricing, scheduling or documented acceptance of lower margin.

No Production activation is authorized here.


## Controlled paid-order intake

Initial controlled hard cap:

- **3 new paid orders per calendar day**

This is a validation cap, not a permanent business limit.

When the daily cap is reached:
- do not reject a qualified customer automatically;
- route the next eligible order to WAITLIST / NEXT_AVAILABLE_SLOT;
- preserve quotation and customer context;
- do not promise a delivery date until the capacity gate passes.

The daily count is only one signal. Scheduling must also consider:
- active projects
- project complexity / requested capacity units
- concurrent builds
- QA queue
- overdue jobs
- support load
- critical incidents
- reserved capacity
- resource pressure

### Evidence-based scale stages

Stage 1:
- 3 paid orders/day

Stage 2:
- up to 5 paid orders/day only after evidence from roughly 20–30 completed/accepted projects shows stable QA, UAT, delivery and support

Stage 3:
- up to 10 paid orders/day only after the same downstream controls remain stable at Stage 2 volume

Any increase remains a human-approved capacity policy change. The engine must not auto-raise the cap.
