import copy
import unittest

from hierarchical_planner import (
    PlanNode,
    ReplanSignal,
    build_hierarchical_plan,
    evaluate_replan_signal,
    execute_plan,
    prepare_replan,
    validate_plan,
)


def node(
    node_id,
    parent_id,
    *,
    action="RUN_TEST",
    capability="cap.test.execute",
    deps=(),
    evidence=None,
    criteria=None,
    risk="LOW",
    reversible=True,
    environment="NON_PRODUCTION",
    uncertainty=0.1,
):
    return PlanNode(
        node_id=node_id,
        parent_id=parent_id,
        action_id=action,
        capability_id=capability,
        evidence_ids=tuple(evidence or (f"urn:evidence:{node_id}",)),
        success_criteria=tuple(criteria or (f"{node_id} verified",)),
        dependencies=tuple(deps),
        risk=risk,
        reversible=reversible,
        environment=environment,
        uncertainty=uncertainty,
        assumptions=(),
    )


def good_nodes():
    return [
        node("root", None, action="READ_ONLY_OBSERVATION", capability="cap.observe.readonly"),
        node("inspect", "root", action="READ_ONLY_OBSERVATION", capability="cap.observe.readonly", deps=("root",)),
        node("test", "root", deps=("root",)),
        node("verify", "test", action="READ_ONLY_OBSERVATION", capability="cap.observe.readonly", deps=("inspect", "test")),
    ]


def good_plan():
    return build_hierarchical_plan(objective_id="obj-1", nodes=good_nodes())


class HierarchicalPlanningTests(unittest.TestCase):
    def test_bounded_hierarchical_plan_is_ready(self):
        out = good_plan()
        self.assertEqual(out["status"], "PLAN_READY")
        self.assertEqual(out["root_node_id"], "root")
        self.assertEqual(out["node_count"], 4)
        self.assertGreaterEqual(len(out["execution_waves"]), 3)
        self.assertEqual(out["execution_authority"], "NONE")
        self.assertFalse(out["execution_performed"])
        self.assertEqual(out["autonomous_ceiling"], "PREPARE_PR")
        self.assertEqual(out["production_authority"], "HUMAN_ONLY")
        self.assertEqual(validate_plan(out)["status"], "READY")

    def test_digest_is_deterministic(self):
        a = good_plan()
        b = good_plan()
        self.assertEqual(a["plan_digest"], b["plan_digest"])

    def test_human_only_action_routes_to_human_gate(self):
        rows = good_nodes()
        rows[2] = node("test", "root", action="PRODUCTION_RELEASE", deps=("root",))
        out = build_hierarchical_plan(objective_id="obj-1", nodes=rows)
        self.assertEqual(out["status"], "HUMAN_GATE")
        self.assertEqual(out["reason"], "HUMAN_ONLY_ACTION_IN_PLAN")

    def test_production_node_routes_to_human_gate(self):
        rows = good_nodes()
        rows[2] = node("test", "root", deps=("root",), environment="PRODUCTION")
        out = build_hierarchical_plan(objective_id="obj-1", nodes=rows)
        self.assertEqual(out["status"], "HUMAN_GATE")
        self.assertEqual(out["reason"], "PRODUCTION_NODE_REQUIRES_HUMAN")

    def test_high_uncertainty_routes_to_human_gate(self):
        rows = good_nodes()
        rows[2] = node("test", "root", deps=("root",), uncertainty=0.9)
        out = build_hierarchical_plan(objective_id="obj-1", nodes=rows)
        self.assertEqual(out["status"], "HUMAN_GATE")
        self.assertEqual(out["reason"], "UNCERTAINTY_REQUIRES_HUMAN_REVIEW")

    def test_missing_evidence_fails_closed(self):
        rows = good_nodes()
        rows[2] = PlanNode(
            node_id="test", parent_id="root", action_id="RUN_TEST",
            capability_id="cap.test.execute", evidence_ids=(),
            success_criteria=("verified",), dependencies=("root",),
        )
        out = build_hierarchical_plan(objective_id="obj-1", nodes=rows)
        self.assertEqual(out["status"], "HOLD")
        self.assertEqual(out["reason"], "NODE_EVIDENCE_REQUIRED")

    def test_parent_must_be_dependency(self):
        rows = good_nodes()
        rows[1] = node("inspect", "root", action="READ_ONLY_OBSERVATION", capability="cap.observe.readonly", deps=())
        out = build_hierarchical_plan(objective_id="obj-1", nodes=rows)
        self.assertEqual(out["reason"], "PARENT_DEPENDENCY_REQUIRED")

    def test_dependency_cycle_fails_closed(self):
        rows = [
            node("root", None, action="READ_ONLY_OBSERVATION", capability="cap.observe.readonly"),
            node("a", "root", deps=("root", "b")),
            node("b", "root", deps=("root", "a")),
        ]
        out = build_hierarchical_plan(objective_id="obj-1", nodes=rows)
        self.assertEqual(out["reason"], "DEPENDENCY_CYCLE")

    def test_replan_signal_requires_fresh_evidence(self):
        p = good_plan()
        s = ReplanSignal(
            plan_digest=p["plan_digest"],
            trigger="VALIDATION_FAILED",
            trigger_evidence_refs=("urn:evidence:failure",),
            completed_node_ids=("root", "inspect"),
            evidence_fresh=False,
            authority_unchanged=True,
            scope_unchanged=True,
            risk="LOW",
        )
        out = evaluate_replan_signal(p, s)
        self.assertEqual(out["status"], "HOLD")
        self.assertEqual(out["reason"], "REPLAN_EVIDENCE_STALE")

    def test_authority_change_routes_to_human(self):
        p = good_plan()
        s = ReplanSignal(
            plan_digest=p["plan_digest"],
            trigger="EVIDENCE_CHANGED",
            trigger_evidence_refs=("urn:evidence:new",),
            completed_node_ids=("root",),
            evidence_fresh=True,
            authority_unchanged=False,
            scope_unchanged=True,
            risk="LOW",
        )
        out = evaluate_replan_signal(p, s)
        self.assertEqual(out["status"], "HUMAN_GATE")
        self.assertEqual(out["reason"], "REPLAN_AUTHORITY_CHANGE_REQUIRES_HUMAN")

    def test_bounded_replan_preserves_scope_and_completed_nodes(self):
        p = good_plan()
        s = ReplanSignal(
            plan_digest=p["plan_digest"],
            trigger="VALIDATION_FAILED",
            trigger_evidence_refs=("urn:evidence:validation-failed",),
            completed_node_ids=("root", "inspect"),
            evidence_fresh=True,
            authority_unchanged=True,
            scope_unchanged=True,
            risk="LOW",
        )
        replacements = [
            node("test", "root", deps=("root",), evidence=("urn:evidence:test:new",), criteria=("test passes after bounded retry",), uncertainty=0.2),
            node("verify", "test", action="READ_ONLY_OBSERVATION", capability="cap.observe.readonly", deps=("inspect", "test"), evidence=("urn:evidence:verify:new",)),
        ]
        out = prepare_replan(p, s, replacements)
        self.assertEqual(out["status"], "REPLAN_READY")
        self.assertEqual(out["replanned_plan"]["lineage"]["parent_plan_digest"], p["plan_digest"])
        self.assertEqual(out["replanned_plan"]["lineage"]["replan_count"], 1)
        old = {x["node_id"]: x for x in p["nodes"]}
        new = {x["node_id"]: x for x in out["replanned_plan"]["nodes"]}
        self.assertEqual(old["root"], new["root"])
        self.assertEqual(old["inspect"], new["inspect"])
        self.assertFalse(out["execution_performed"])

    def test_replan_scope_widening_routes_to_human(self):
        p = good_plan()
        s = ReplanSignal(
            plan_digest=p["plan_digest"],
            trigger="TOOL_UNAVAILABLE",
            trigger_evidence_refs=("urn:evidence:tool",),
            completed_node_ids=("root", "inspect"),
            evidence_fresh=True,
            authority_unchanged=True,
            scope_unchanged=True,
            risk="LOW",
        )
        replacements = [
            node("test", "root", action="GENERATE_ARTIFACT", capability="cap.artifact.generate", deps=("root",)),
            node("verify", "test", action="READ_ONLY_OBSERVATION", capability="cap.observe.readonly", deps=("inspect", "test")),
        ]
        out = prepare_replan(p, s, replacements)
        self.assertEqual(out["status"], "HUMAN_GATE")
        self.assertEqual(out["reason"], "REPLAN_SCOPE_WIDENING_FORBIDDEN")

    def test_tampered_plan_rejected(self):
        p = good_plan()
        tampered = copy.deepcopy(p)
        tampered["execution_authority"] = "EXECUTE"
        self.assertEqual(validate_plan(tampered)["status"], "HOLD")

    def test_planner_cannot_execute(self):
        with self.assertRaisesRegex(PermissionError, "HIERARCHICAL_PLANNER_EXECUTION_FORBIDDEN"):
            execute_plan()


if __name__ == "__main__":
    unittest.main()
