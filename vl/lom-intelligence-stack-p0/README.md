# LOM Intelligence Stack P0

Status: DEVELOPMENT / NON-PRODUCTION

## Purpose

Increase LOM's effective foundation-model intelligence without training a frontier-scale foundation model from scratch.

P0 adds an evidence-bound intelligence layer above the existing Agentic OS model/tool router. It does **not** create a second execution router.

Core responsibilities:

1. maintain a versioned, vendor-neutral Model Registry;
2. record benchmark evidence for exact model + version + task class;
3. reject stale, self-reported marketing, malformed, or insufficient benchmark evidence;
4. compile only eligible benchmark-backed routes into the existing Agentic OS `ModelRoute` contract;
5. preserve the existing authority boundary.

## Intelligence principle

LOM does not ask "Which model is best?"

LOM asks:

> For this exact task class, with these quality, reliability, evidence, latency and cost requirements, which currently certified model/version has fresh measured evidence?

No global winner is stored.

## P0 benchmark domains

The benchmark manifest defines initial task families:

- coding and debugging;
- cadastral reasoning;
- geospatial/GIS reasoning;
- surveying computation and fieldbook interpretation;
- document extraction and evidence-grounded synthesis;
- business workflow reasoning;
- general tool-use/retrieval;
- adversarial hallucination and evidence traps.

The benchmark manifest defines test requirements only. It contains no fabricated provider scores.

## Composition with existing Agentic OS

Existing canonical routing remains owned by:

`vl/lom-agentic-os-p0/intelligence_core.py`

P0 Intelligence Stack emits route records compatible with the existing `ModelRoute` fields:

- route_id
- provider
- certified
- supported
- non_production_only
- quality
- reliability
- latency
- cost

The Agentic OS still owns plan construction, tool eligibility, checkpoints, independent verification and authority decisions.

## Benchmark evidence rules

A benchmark result is eligible only when all of the following are true:

- exact model ID and version match the registry;
- dataset ID, version and digest are present;
- evidence reference is addressable;
- evidence is fresh;
- evaluator identity is present;
- evidence origin is `LOM_EVAL` or `EXTERNAL_VERIFIED`;
- sample count meets the task request minimum;
- all numeric metrics are finite and in range;
- minimum quality, reliability, evidence correctness and tool success gates pass;
- maximum hallucination, latency and cost gates pass when specified.

Marketing claims and provider self-reporting are never routing evidence.

## Registry rules

The registry stores metadata only. It MUST NOT contain:

- API keys;
- access tokens;
- Production credentials;
- hidden system prompts;
- customer secrets.

A model is route-eligible only when it is supported, certified, security-reviewed, license-cleared, and bounded to non-Production in P0.

## Authority invariants

- autonomous ceiling: `PREPARE_PR`
- execution authority: `NONE`
- Production authority: `HUMAN_ONLY`
- protected-main merge: `HUMAN_ONLY`
- self-approval: `FORBIDDEN`
- credentials in registry: `FORBIDDEN`
- fabricated benchmark scores: `FORBIDDEN`

## P0 lifecycle

`REGISTER → BENCHMARK → VALIDATE → ELIGIBILITY GATE → COMPILE ROUTES → EXISTING AGENTIC ROUTER → INDEPENDENT VERIFY → LEARN`

P0 does not fine-tune models. Later phases may add RAG intelligence, critic/verifier ensembles, failure datasets, distillation and specialist adapters only after this benchmark foundation is reliable.
