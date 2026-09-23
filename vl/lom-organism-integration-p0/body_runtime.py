from __future__ import annotations

from typing import Any, Callable, Iterable

from organism import ORGANS, SensorySignal, build_reflex_plan, digest, homeostasis, route_signal

BODY_RUNTIME_SCHEMA = "lom.organism-runtime/1"
BOUNDED_DELEGATION_SCHEMA = "lom.organism-bounded-delegation/1"

OrganProbe = Callable[[], dict[str, Any]]
BoundedExecutor = Callable[[dict[str, Any]], dict[str, Any]]
EvidenceRecorder = Callable[[dict[str, Any]], dict[str, Any]]
LearningSink = Callable[[dict[str, Any]], dict[str, Any]]
HumanReviewSink = Callable[[dict[str, Any]], dict[str, Any]]
SignalSource = Callable[[], Iterable[SensorySignal]]


class BodyRuntime:
    """Fail-closed coordinator that binds existing LOM organs without replacing them.

    The runtime owns no Production authority. It can delegate only bounded,
    non-Production preparation to an injected executor that is expected to be
    backed by the existing ACP / Agentic OS Hands boundary.
    """

    def __init__(
        self,
        registry: dict[str, Any],
        *,
        organ_probes: dict[str, OrganProbe],
        bounded_executor: BoundedExecutor | None = None,
        evidence_recorder: EvidenceRecorder | None = None,
        learning_sink: LearningSink | None = None,
        human_review_sink: HumanReviewSink | None = None,
        signal_source: SignalSource | None = None,
    ) -> None:
        self.registry = registry
        self.organ_probes = dict(organ_probes)
        self.bounded_executor = bounded_executor
        self.evidence_recorder = evidence_recorder
        self.learning_sink = learning_sink
        self.human_review_sink = human_review_sink
        self.signal_source = signal_source

    def collect_organ_states(self) -> dict[str, Any]:
        states: list[dict[str, Any]] = []
        errors: list[str] = []

        unknown = sorted(set(self.organ_probes) - ORGANS)
        for organ in unknown:
            errors.append(f"UNKNOWN_ORGAN_PROBE:{organ}")

        for organ in sorted(ORGANS):
            probe = self.organ_probes.get(organ)
            if probe is None:
                errors.append(f"MISSING_ORGAN_PROBE:{organ}")
                continue
            try:
                row = probe()
            except Exception as exc:
                errors.append(f"ORGAN_PROBE_FAILED:{organ}:{type(exc).__name__}")
                continue
            if not isinstance(row, dict):
                errors.append(f"ORGAN_PROBE_INVALID:{organ}")
                continue
            if row.get("organ") != organ:
                errors.append(f"ORGAN_PROBE_ID_MISMATCH:{organ}")
                continue
            states.append(dict(row))

        return {
            "schema": "lom.organism-probe-snapshot/1",
            "states": states,
            "errors": errors,
            "probed_organs": sorted(row["organ"] for row in states),
        }

    def _load_signals(
        self,
        signals: Iterable[SensorySignal] | None,
        *,
        max_signals: int,
    ) -> tuple[list[SensorySignal], list[str]]:
        errors: list[str] = []
        if max_signals <= 0:
            return [], ["MAX_SIGNALS_INVALID"]

        if signals is None:
            if self.signal_source is None:
                items: list[Any] = []
            else:
                try:
                    items = list(self.signal_source())
                except Exception as exc:
                    return [], [f"SIGNAL_SOURCE_FAILED:{type(exc).__name__}"]
        else:
            items = list(signals)

        if len(items) > max_signals:
            return [], ["SIGNAL_BATCH_LIMIT_EXCEEDED"]

        out: list[SensorySignal] = []
        seen_ids: set[str] = set()
        for item in items:
            if not isinstance(item, SensorySignal):
                errors.append("INVALID_SIGNAL_ENVELOPE")
                continue
            if item.signal_id in seen_ids:
                errors.append(f"DUPLICATE_SIGNAL_ID:{item.signal_id}")
                continue
            seen_ids.add(item.signal_id)
            out.append(item)
        return out, errors

    def _record(self, phase: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.evidence_recorder is None:
            return {"decision": "HOLD", "reason": "EVIDENCE_RECORDER_UNAVAILABLE"}
        envelope = {
            "schema": "lom.organism-runtime-evidence/1",
            "phase": phase,
            "payload": payload,
            "payload_digest": digest(payload),
        }
        try:
            result = self.evidence_recorder(envelope)
        except Exception as exc:
            return {
                "decision": "HOLD",
                "reason": "EVIDENCE_RECORD_FAILED",
                "error_type": type(exc).__name__,
            }
        if not isinstance(result, dict) or not result.get("evidence_id"):
            return {"decision": "HOLD", "reason": "EVIDENCE_RECEIPT_REQUIRED"}
        return {
            "decision": "ALLOW",
            "evidence_id": str(result["evidence_id"]),
            "detail": result,
        }

    def _prepare_human_review(self, route: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
        package = {
            "schema": "lom.organism-human-review/1",
            "signal_id": route.get("signal_id"),
            "project_id": route.get("project_id"),
            "reason": route.get("reason"),
            "requested_action": route.get("requested_action"),
            "route_digest": route.get("route_digest"),
            "evidence_refs": route.get("evidence_refs") or [],
            "steps": plan.get("steps") or [],
            "authority": "HUMAN_ONLY",
        }
        if self.human_review_sink is None:
            return {
                "decision": "HUMAN_REVIEW",
                "reason": "VOICE_SINK_UNAVAILABLE",
                "package": package,
            }
        try:
            receipt = self.human_review_sink(package)
        except Exception as exc:
            return {
                "decision": "HUMAN_REVIEW",
                "reason": "VOICE_SINK_FAILED",
                "error_type": type(exc).__name__,
                "package": package,
            }
        return {
            "decision": "HUMAN_REVIEW",
            "reason": "HUMAN_DECISION_PACKAGE_PREPARED",
            "package": package,
            "receipt": receipt if isinstance(receipt, dict) else {"raw_type": type(receipt).__name__},
        }

    def _delegate_bounded(self, route: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
        if self.bounded_executor is None:
            return {"decision": "HOLD", "reason": "BOUNDED_EXECUTOR_UNAVAILABLE"}
        if self.learning_sink is None:
            return {"decision": "HOLD", "reason": "LEARNING_SINK_UNAVAILABLE"}

        request = {
            "schema": BOUNDED_DELEGATION_SCHEMA,
            "signal_id": route["signal_id"],
            "project_id": route["project_id"],
            "route_digest": route["route_digest"],
            "requested_action": route.get("requested_action"),
            "steps": plan.get("steps") or [],
            "max_authority": "PREPARE_PR",
            "production": False,
            "production_locked": True,
            "idempotency_key": route["route_digest"],
            "evidence_refs": route.get("evidence_refs") or [],
        }

        try:
            result = self.bounded_executor(request)
        except Exception as exc:
            return {
                "decision": "HOLD",
                "reason": "BOUNDED_EXECUTOR_FAILED",
                "error_type": type(exc).__name__,
                "request": request,
            }

        if not isinstance(result, dict):
            return {"decision": "HOLD", "reason": "BOUNDED_EXECUTOR_INVALID_RESULT", "request": request}
        if result.get("decision") != "ALLOW":
            return {
                "decision": "HOLD",
                "reason": "BOUNDED_EXECUTOR_DENIED",
                "request": request,
                "executor_result": result,
            }
        if result.get("production_locked") is not True or result.get("production") is True:
            return {
                "decision": "HOLD",
                "reason": "EXECUTOR_PRODUCTION_BOUNDARY_UNPROVEN",
                "request": request,
                "executor_result": result,
            }
        if not (result.get("action_digest") or result.get("evidence_id") or result.get("evidence_refs")):
            return {
                "decision": "HOLD",
                "reason": "EXECUTOR_EVIDENCE_REQUIRED",
                "request": request,
                "executor_result": result,
            }

        learning = {
            "schema": "lom.organism-learning-proposal/1",
            "signal_id": route["signal_id"],
            "project_id": route["project_id"],
            "route_digest": route["route_digest"],
            "executor_evidence": (
                result.get("action_digest")
                or result.get("evidence_id")
                or result.get("evidence_refs")
            ),
            "proposal_only": True,
            "authority_change": "FORBIDDEN",
            "max_authority": "PREPARE_PR",
        }
        try:
            learned = self.learning_sink(learning)
        except Exception as exc:
            return {
                "decision": "HOLD",
                "reason": "LEARNING_SINK_FAILED",
                "error_type": type(exc).__name__,
                "request": request,
                "executor_result": result,
            }
        if not isinstance(learned, dict) or learned.get("proposal_only") is not True:
            return {
                "decision": "HOLD",
                "reason": "LEARNING_AUTHORITY_WEAKENED",
                "request": request,
                "executor_result": result,
                "learning_result": learned,
            }
        if learned.get("authority_change_applied") is True:
            return {
                "decision": "HOLD",
                "reason": "LEARNING_AUTHORITY_CHANGE_FORBIDDEN",
                "request": request,
                "executor_result": result,
                "learning_result": learned,
            }

        return {
            "decision": "ALLOW",
            "reason": "BOUNDED_PREPARATION_VERIFIED",
            "request": request,
            "executor_result": result,
            "learning_result": learned,
        }

    def cycle(
        self,
        *,
        now_epoch: int,
        max_age_seconds: int,
        signals: Iterable[SensorySignal] | None = None,
        max_signals: int = 100,
    ) -> dict[str, Any]:
        probe_snapshot = self.collect_organ_states()
        body = homeostasis(
            self.registry,
            probe_snapshot["states"],
            now_epoch=now_epoch,
            max_age_seconds=max_age_seconds,
        )

        signal_items, signal_errors = self._load_signals(signals, max_signals=max_signals)
        preflight = {
            "body_status": body.get("status"),
            "body_digest": body.get("homeostasis_digest"),
            "probe_errors": probe_snapshot["errors"],
            "signal_errors": signal_errors,
            "signal_ids": [item.signal_id for item in signal_items],
            "autonomous_ceiling": "PREPARE_PR",
            "production_authority": "HUMAN_ONLY",
        }

        if body.get("status") in {"HOLD", "FAILED"} or probe_snapshot["errors"]:
            return self._final_result(
                "HOLD",
                "HOMEOSTASIS_BLOCK",
                body=body,
                probe_snapshot=probe_snapshot,
                signal_errors=signal_errors,
                routes=[],
                plans=[],
                actions=[],
                preflight_record=None,
                final_record=None,
            )

        if signal_errors:
            return self._final_result(
                "HOLD",
                "SIGNAL_INTAKE_BLOCK",
                body=body,
                probe_snapshot=probe_snapshot,
                signal_errors=signal_errors,
                routes=[],
                plans=[],
                actions=[],
                preflight_record=None,
                final_record=None,
            )

        preflight_record = self._record("PREFLIGHT", preflight)
        if preflight_record["decision"] != "ALLOW":
            return self._final_result(
                "HOLD",
                preflight_record["reason"],
                body=body,
                probe_snapshot=probe_snapshot,
                signal_errors=[],
                routes=[],
                plans=[],
                actions=[],
                preflight_record=preflight_record,
                final_record=None,
            )

        routes: list[dict[str, Any]] = []
        plans: list[dict[str, Any]] = []
        actions: list[dict[str, Any]] = []
        cycle_status = "MONITOR"
        cycle_reason = "NO_ACTIONABLE_SIGNAL"

        for signal in signal_items:
            route = route_signal(signal, now_epoch=now_epoch)
            plan = build_reflex_plan(route)
            routes.append(route)
            plans.append(plan)

            if route["action_class"] == "HOLD":
                cycle_status = "HOLD"
                cycle_reason = route["reason"]
                actions.append({"decision": "HOLD", "reason": route["reason"], "signal_id": signal.signal_id})
                break

            if route["action_class"] == "HUMAN_REVIEW":
                review = self._prepare_human_review(route, plan)
                actions.append(review)
                if cycle_status != "HOLD":
                    cycle_status = "HUMAN_REVIEW"
                    cycle_reason = route["reason"]
                continue

            if plan.get("status") == "PREPARE_PR":
                if body.get("status") != "HEALTHY":
                    cycle_status = "HOLD"
                    cycle_reason = "BODY_DEGRADED_EXECUTION_BLOCKED"
                    actions.append({
                        "decision": "HOLD",
                        "reason": "BODY_DEGRADED_EXECUTION_BLOCKED",
                        "signal_id": signal.signal_id,
                    })
                    break
                action = self._delegate_bounded(route, plan)
                actions.append(action)
                if action["decision"] != "ALLOW":
                    cycle_status = "HOLD"
                    cycle_reason = action["reason"]
                    break
                if cycle_status not in {"HOLD", "HUMAN_REVIEW"}:
                    cycle_status = "PREPARED"
                    cycle_reason = "BOUNDED_NONPROD_PREPARATION_COMPLETE"

        final_payload = {
            "schema": BODY_RUNTIME_SCHEMA,
            "status": cycle_status,
            "reason": cycle_reason,
            "body_status": body.get("status"),
            "body_digest": body.get("homeostasis_digest"),
            "preflight_evidence_id": preflight_record.get("evidence_id"),
            "route_digests": [route.get("route_digest") for route in routes],
            "action_reasons": [action.get("reason") for action in actions],
            "autonomous_ceiling": "PREPARE_PR",
            "production_authority": "HUMAN_ONLY",
            "protected_main_merge": "HUMAN_ONLY",
        }
        final_record = self._record("FINAL", final_payload)
        if final_record["decision"] != "ALLOW":
            cycle_status = "HOLD"
            cycle_reason = final_record["reason"]

        return self._final_result(
            cycle_status,
            cycle_reason,
            body=body,
            probe_snapshot=probe_snapshot,
            signal_errors=[],
            routes=routes,
            plans=plans,
            actions=actions,
            preflight_record=preflight_record,
            final_record=final_record,
        )

    def _final_result(
        self,
        status: str,
        reason: str,
        *,
        body: dict[str, Any],
        probe_snapshot: dict[str, Any],
        signal_errors: list[str],
        routes: list[dict[str, Any]],
        plans: list[dict[str, Any]],
        actions: list[dict[str, Any]],
        preflight_record: dict[str, Any] | None,
        final_record: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload = {
            "schema": BODY_RUNTIME_SCHEMA,
            "status": status,
            "reason": reason,
            "body_status": body.get("status"),
            "body": body,
            "probe_errors": probe_snapshot.get("errors") or [],
            "signal_errors": signal_errors,
            "routes": routes,
            "plans": plans,
            "actions": actions,
            "preflight_record": preflight_record,
            "final_record": final_record,
            "autonomous_ceiling": "PREPARE_PR",
            "production_authority": "HUMAN_ONLY",
            "protected_main_merge": "HUMAN_ONLY",
            "financial_contractual_customer_commitment": "HUMAN_ONLY",
        }
        return {**payload, "cycle_digest": digest(payload)}
