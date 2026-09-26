#!/usr/bin/env python3
import unittest

from customer_action_gateway import (
    accept_uat,
    gateway_can_mutate_authoritative_state,
    request_change,
    route_customer_action,
)


BASE = dict(
    actor_id="CUS-USER-001",
    actor_org="ORG-001",
    resource_org="ORG-001",
    role="PROJECT_MANAGER",
    project_id="LD-PROJECT-001",
)


class CustomerActionGatewayTests(unittest.TestCase):
    def test_change_request_prepares_ledger_intake_only(self):
        r = request_change(
            **BASE,
            base_scope_version=1,
            requested_change="Add second approval workflow",
            submitted_at="2026-09-26T11:00:00+08:00",
            idempotency_key="change-001",
        )
        self.assertEqual(r["decision"], "ALLOW")
        self.assertEqual(r["handoff"], "LD_CHANGE_REQUEST_SCOPE_LEDGER")
        self.assertEqual(r["record"]["state"], "REQUESTED")
        self.assertIsNone(r["record"]["decision"])
        self.assertFalse(r["source_truth_mutated"])

    def test_change_request_cross_org_denied(self):
        d = dict(BASE)
        d["resource_org"] = "ORG-OTHER"
        r = request_change(
            **d,
            base_scope_version=1,
            requested_change="Change scope",
            submitted_at="2026-09-26T11:00:00+08:00",
            idempotency_key="change-002",
        )
        self.assertEqual(r["decision"], "DENY")
        self.assertEqual(r["reason"], "TENANT_BOUNDARY")

    def test_viewer_cannot_submit_project_change(self):
        d = dict(BASE)
        d["role"] = "VIEWER"
        r = request_change(
            **d,
            base_scope_version=1,
            requested_change="Change scope",
            submitted_at="2026-09-26T11:00:00+08:00",
            idempotency_key="change-003",
        )
        self.assertEqual(r["decision"], "DENY")

    def test_change_request_replay_is_idempotent(self):
        r = request_change(
            **BASE,
            base_scope_version=1,
            requested_change="Change scope",
            submitted_at="2026-09-26T11:00:00+08:00",
            idempotency_key="change-004",
            consumed_keys=frozenset({"change-004"}),
        )
        self.assertEqual(r["decision"], "IDEMPOTENT_REPLAY")

    def test_uat_acceptance_reuses_lifecycle_gate(self):
        r = accept_uat(
            **BASE,
            current_state="QA_PASSED",
            acceptance_evidence_ref="EVID-UAT-001",
            accepted_at="2026-09-26T11:05:00+08:00",
            idempotency_key="uat-001",
        )
        self.assertEqual(r["decision"], "ALLOW")
        self.assertEqual(r["handoff"], "LD_INTEGRATED_CUSTOMER_LIFECYCLE_GATE")
        self.assertEqual(r["receipt"]["to_state"], "CUSTOMER_ACCEPTED")
        self.assertFalse(r["source_truth_mutated"])

    def test_uat_acceptance_requires_qa_passed(self):
        r = accept_uat(
            **BASE,
            current_state="BUILDING",
            acceptance_evidence_ref="EVID-UAT-002",
            accepted_at="2026-09-26T11:05:00+08:00",
            idempotency_key="uat-002",
        )
        self.assertEqual(r["decision"], "HOLD")
        self.assertEqual(r["reason"], "UAT_ACCEPTANCE_NOT_CURRENTLY_ELIGIBLE")

    def test_uat_replay_does_not_create_second_transition(self):
        r = accept_uat(
            **BASE,
            current_state="QA_PASSED",
            acceptance_evidence_ref="EVID-UAT-003",
            accepted_at="2026-09-26T11:05:00+08:00",
            idempotency_key="uat-003",
            consumed_keys=frozenset({"uat-003"}),
        )
        self.assertEqual(r["decision"], "IDEMPOTENT_REPLAY")
        self.assertFalse(r["source_truth_mutated"])

    def test_unknown_action_fails_closed(self):
        r = route_customer_action("PAY_NOW")
        self.assertEqual(r["decision"], "HOLD")
        self.assertEqual(r["reason"], "CUSTOMER_ACTION_UNSUPPORTED")

    def test_gateway_has_no_authoritative_mutation_power(self):
        self.assertFalse(gateway_can_mutate_authoritative_state())


if __name__ == "__main__":
    unittest.main()
