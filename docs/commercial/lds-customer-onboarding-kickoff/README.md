# LD Customer Onboarding / Project Kickoff Gate v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: prevent a paid project from entering BUILDING before it is actually ready.

## Key principle

Payment != project readiness.

The project must have:
- approved scope snapshot
- confirmed acceptance criteria
- milestone funding evidence
- customer and LD owners
- confirmed communication channel
- required dependencies
- required access
- target environment
- data-handling requirements
- kickoff record

## Readiness states

NOT_READY
CLIENT_ACTION_REQUIRED
LD_ACTION_REQUIRED
READY_FOR_KICKOFF
KICKED_OFF

## Delay handling

If a required customer dependency is missing, the project enters CLIENT_ACTION_REQUIRED. Delivery time must not continue being silently consumed. A material delay requires schedule/ETA rebaseline before a new commitment is made.

## Security

Do not collect passwords, API keys or secrets through ordinary onboarding documents. Use approved secure access-transfer mechanisms.

## Authority

READY_FOR_KICKOFF does not itself start BUILDING. Human kickoff approval is still required. Kickoff does not grant Production deployment or release authority.
