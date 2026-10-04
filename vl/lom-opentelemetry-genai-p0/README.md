# LOM P0-C — OpenTelemetry GenAI Adapter

Status: DEVELOPMENT / NON-PRODUCTION / READ-ONLY TELEMETRY ADAPTER

## Objective

Translate existing LOM measured trace evidence into an OpenTelemetry-compatible GenAI telemetry envelope without creating a new source of truth or changing execution authority.

LOM Evidence Fabric, Event Ledger, Macro Evaluation and Causal Memory remain canonical. This adapter is export-only.

## Baseline

P0-C follows the current OpenTelemetry semantic-convention direction for GenAI:

- `gen_ai.operation.name`
- `gen_ai.provider.name`
- `gen_ai.request.model`
- `gen_ai.response.model`
- `gen_ai.usage.input_tokens`
- `gen_ai.usage.output_tokens`
- tool execution represented with `gen_ai.operation.name=execute_tool`

## Privacy-first profile

P0-C does NOT export by default:

- prompt/input message content;
- completion/output message content;
- system instructions;
- retrieval query text;
- tool arguments/results;
- secrets or credentials;
- production-sensitive payload content.

Only measured metadata is emitted.

## LOM extensions

The following namespaced attributes preserve LOM-specific governance/evidence:

- `lom.project.id`
- `lom.task.class`
- `lom.trace.id`
- `lom.evidence.refs`
- `lom.independently_validated`
- `lom.correctness`
- `lom.safety`
- `lom.evidence_correctness`
- `lom.tool.success`
- `lom.cost.usd`
- `lom.failure.code`

## Authority

- autonomous ceiling: PREPARE_PR
- execution authority: NONE
- Production authority: HUMAN_ONLY
- protected-main merge: HUMAN_ONLY
- network export: DISABLED in P0
- telemetry persistence: NONE
- prompt/completion content capture: DISABLED

P0-C builds deterministic telemetry records only. Actual OTLP network export is a later governed integration.
