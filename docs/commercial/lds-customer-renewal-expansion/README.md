# LD Customer Renewal & Expansion Intelligence v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: identify evidence-backed renewal, retention and expansion opportunities after delivery without turning customer success into automatic sales outreach.

## Inputs

- support/maintenance plan expiry
- confirmed customer satisfaction
- unresolved support issues
- adoption evidence
- new workflow need
- Change Request history
- profitability
- delivery capacity

## Decision paths

RENEWAL_REVIEW
RETENTION_FOLLOW_UP
EXPANSION_REVIEW
NO_ACTION
HOLD

## Core rule

Unresolved support or satisfaction issues come before upsell.

A customer who has a problem is routed to retention/support follow-up, not automatically targeted for an expansion offer.

## Human authority

This engine cannot:
- contact the customer;
- renew a plan;
- upgrade service;
- create a binding offer;
- change price or discount;
- bypass Blueprint, Change Request, Pricing or Capacity gates.

Customer acceptance and human commercial approval remain required.
