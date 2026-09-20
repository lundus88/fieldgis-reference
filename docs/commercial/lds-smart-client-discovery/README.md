# LD Smart Client Discovery v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: convert a qualified lead's plain-language request into a structured, reviewable requirement brief with minimum customer friction.

## Core principle

**Ask only what changes the solution.**

The engine must not ask questions merely because a field exists. A question is justified only when its answer can materially affect:
- solution type
- scope
- pricing basis
- delivery effort
- dependency
- legal/compliance handling
- customer acceptance criteria
- implementation risk

## Position in the LD flow

QUALIFIED_LEAD
→ SMART_CLIENT_DISCOVERY
→ REQUIREMENT_BRIEF_DRAFT
→ CUSTOMER_CONFIRMATION
→ SCOPE_REVIEW
→ QUOTATION

This module does not grant quotation approval, payment authority, Production authority, deployment authority, or contract acceptance authority.

## Progressive discovery

Target:
- 5–8 primary questions for a normal project
- only relevant follow-up questions
- no fixed long questionnaire
- allow free-text descriptions in ordinary language
- infer candidate requirements from the customer's own wording, then confirm them rather than repeatedly asking the customer to restate the same information

## Canonical discovery dimensions

1. Problem / desired outcome
2. Solution category
3. Primary users
4. Required capabilities
5. Existing assets / systems / data
6. Examples / design direction
7. Commercial constraints: budget band, urgency, phased delivery
8. Risk / compliance / integration dependencies when relevant

## Adaptive branching

Examples:
- Website → pages, lead capture, content ownership, domain/hosting, multilingual needs
- E-commerce → catalogue, payment, fulfilment, inventory, tax/shipping dependencies
- AI / automation → process to automate, input/output, human approval points, data sensitivity, failure handling
- Business system / portal → roles, workflow states, records, permissions, integrations, reporting
- Existing-system enhancement → current stack, pain points, migration constraints, backward compatibility

Irrelevant branches must not be shown.

## Requirement Brief

Minimum output:
- customer-stated objective
- interpreted solution type
- target users
- must-have requirements
- optional requirements
- known exclusions
- existing assets
- integrations / dependencies
- data sensitivity / compliance flags
- delivery constraints
- assumptions
- unresolved questions
- acceptance criteria draft
- confidence state
- customer confirmation state

## Confidence and confirmation

Possible states:
- DISCOVERY_IN_PROGRESS
- READY_FOR_CUSTOMER_CONFIRMATION
- CUSTOMER_CONFIRMED
- NEEDS_HUMAN_REVIEW
- INSUFFICIENT_INFORMATION
- DECLINED_OR_UNSUPPORTED

The system must never silently convert an inference into a confirmed requirement.

Customer confirmation should show a concise summary:
- what LD understands
- what is included
- what is optional
- what is still unknown

The customer must be able to Confirm or Edit before the requirement brief can be treated as confirmed.

## Privacy minimisation

Do not request sensitive personal, financial, credential, production-secret, or regulated data unless it is materially required and the approved secure collection path exists.

Never ask for:
- passwords
- private API secrets
- full payment-card details
- unnecessary identity documents
- production database dumps as a default discovery step

Where sensitive integration is relevant, ask about the type of integration and sensitivity classification first, not the secret itself.

## Human-review triggers

Force NEEDS_HUMAN_REVIEW when:
- legal/regulatory interpretation materially changes the build
- high-risk personal or confidential data is involved
- the customer asks LD to bypass a platform, security, contractual, or legal control
- requirements materially contradict each other
- scope is too ambiguous for defensible quotation
- integration feasibility is unverified and commercially material

## Commercial boundary

This engine may produce:
- requirement brief
- scope candidates
- complexity indicators
- open-question list
- recommended offer family

It may not:
- issue an authoritative quotation
- approve a contract
- accept payment
- promise a delivery date
- guarantee feasibility
- activate Production

## Customer experience

Preferred interaction:

Customer:
"I want a website for my contracting company."

LD:
"What should the website achieve first: generate enquiries, provide quotations, sell directly, or something else?"

The next question depends on that answer.

The intended outcome is:
**Tell us what you want → Smart questions → LD understands → LD proposes → Customer confirms → Scope/Quotation.**
