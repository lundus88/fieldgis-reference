# LD Collections & Cashflow Control v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: give LD an evidence-backed view of receivables, overdue exposure and funded milestones without conflating overdue payment with fraud or allowing uncontrolled collection actions.

## Receivable states

NOT_DUE
DUE_SOON
DUE
OVERDUE
DISPUTED
PAID
CANCELLED
REFUNDED

## Core rules

- PAID requires authoritative reconciliation;
- partial payment is not fully paid;
- disputed invoices pause automated reminders;
- overdue is not fraud evidence;
- reminder cadence/channel must be approved;
- reminders are prepared, not autonomously sent, unless a separately approved automation policy exists;
- collections logic cannot change invoice amounts, waive debt, refund, suspend service or threaten legal action.

## Cashflow view

The future dashboard should separate:
- total invoiced
- due soon
- due today
- overdue
- disputed
- collected
- refunded/cancelled
- funded milestones

No Production activation is authorized by this package.
