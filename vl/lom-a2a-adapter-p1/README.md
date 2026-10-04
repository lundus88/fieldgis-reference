# LOM P1 — Governed A2A Interoperability Adapter

Status: DEVELOPMENT / NON-PRODUCTION / METADATA-ONLY

## Objective

Add Agent2Agent (A2A) v1.0 interoperability awareness to LOM without granting an external agent authority, credentials, live delegation, or execution access.

A2A is complementary to MCP:

- MCP standardizes access to tools/resources.
- A2A standardizes communication between independent agents.

LOM keeps its existing Agent Control Plane, Action Registry, Connector Registry, Policy-as-Code and human gates as the authority source.

## Protocol baseline

- A2A protocol version: `1.0`
- release baseline: `v1.0.0`

P1 normalizes:

- Agent Card identity;
- supported interfaces;
- capabilities;
- skill metadata;
- Message metadata;
- Task state;
- Artifact metadata.

## Authority rule

An external Agent Card is discovery evidence, not permission.

A skill becomes eligible only if the exact A2A skill ID has a local LOM binding to:

- a certified read-only A2A fixture connector;
- canonical action `READ_ONLY_OBSERVATION`;
- canonical capability `cap.observe.readonly`;
- an already-permitted local resource scope.

Agent claims, tags, descriptions and capabilities never widen LOM authority.

## Sensitive states

- `TASK_STATE_INPUT_REQUIRED` → HUMAN_GATE
- `TASK_STATE_AUTH_REQUIRED` → HUMAN_GATE

LOM never auto-supplies credentials or auto-answers authorization/input requests in P1.

## Message / artifact semantics

Messages are communication only and are never treated as authoritative outputs.

Artifact content remains unavailable to P1 and requires normal LOM evidence verification before it can influence a consequential decision.

## Explicitly disabled

- live A2A HTTP/JSON-RPC/gRPC connection;
- live SendMessage / streaming;
- credential acquisition or forwarding;
- task cancel/update/runtime;
- external agent delegation;
- write-capable external skills;
- Production actions.

## Authority

- autonomous ceiling: PREPARE_PR
- execution authority: NONE
- Production authority: HUMAN_ONLY
- protected-main merge: HUMAN_ONLY
- network access: DISABLED
- credentials: NONE
- external delegation: DISABLED
- external agent authority trusted: false
