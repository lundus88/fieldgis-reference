#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-autonomous-operations")
errors=[]
required=[
    "README.md","contract.json","capability_registry.json","engine.py","test_engine.py","check_engine.py",
    "value_adds.json","intent_compiler.py","exception_autopilot.py","completion_gate.py",
    "automation_extensions.py","test_value_adds.py",
    "governance_closure.json","governance_closure.py","test_governance_closure.py",
    "sample_order.json","e2e_simulation.py","test_e2e_simulation.py"
]
for f in required:
    if not (root/f).is_file(): errors.append(f"missing {f}")

if (root/"contract.json").exists():
    c=json.loads((root/"contract.json").read_text())
    if c.get("schema")!="lds.autonomous-operations/1": errors.append("schema drift")
    if c.get("operating_principle")!="Client triggers the business. LD runs the workflow. Human governs exceptions and authority gates.":
        errors.append("operating principle drift")
    if c.get("outcome_principle")!="Reliable customer outcome first. Automation is the scaling mechanism.":
        errors.append("outcome principle drift")
    if c.get("action_modes")!=["AUTO","AUTO_NOTIFY","HUMAN_GATE"]:
        errors.append("action mode drift")
    if c.get("closed_loop")!=["DISCOVER","UNDERSTAND","SIMULATE","AUTHORIZE","PLAN","EXECUTE","VERIFY","RECOVER","DELIVER","SUPPORT","LEARN","OPTIMIZE"]:
        errors.append("closed loop drift")
    expected_components={
      "capability_service_registry","capacity_queue_manager","outcome_acceptance_engine",
      "operations_control_tower","autonomous_recovery_rollback","unit_economics_profit_guard",
      "intent_to_execution_compiler","exception_autopilot","evidence_driven_completion_gate",
      "customer_dependency_automation","sla_deadline_guardian","autonomous_tool_model_router",
      "learning_optimization_loop","commercial_recovery_engine",
      "autonomous_change_impact_analyzer","global_kill_switch_circuit_breaker",
      "policy_as_code_governance_engine","identity_credential_permission_broker",
      "software_supply_chain_provenance_guard","continuous_resilience_chaos_verification",
      "customer_portability_exit_guarantee","autonomous_business_health_governor"
    }
    if set(c.get("components",{}).keys())!=expected_components:
        errors.append("autonomous component set incomplete")
    a=c.get("authority",{})
    for key in [
      "learning_policy_mutation","automatic_customer_charge","automatic_contract_mutation",
      "automatic_compensation","production_deployment","live_charging",
      "contract_exception_approval","destructive_production_action",
      "privilege_widening","production_admin_lease","customer_commitment_mutation"
    ]:
        if a.get(key) is not False: errors.append(f"{key} must remain false")
    if c.get("no_idle_policy",{}).get("documented_blocker_required") is not True:
        errors.append("no-idle blocker rule missing")

if (root/"capability_registry.json").exists():
    r=json.loads((root/"capability_registry.json").read_text())
    ids={x.get("id") for x in r.get("capabilities",[])}
    if ids!={"LD_LAUNCH","LD_AUTOMATE","LD_AI","LD_SYSTEM","LD_DISCOVERY"}:
        errors.append("capability registry drift")
    for item in r.get("capabilities",[]):
        if item.get("default_action_mode") not in {"AUTO","AUTO_NOTIFY","HUMAN_GATE"}:
            errors.append("invalid default action mode")

if (root/"value_adds.json").exists():
    v=json.loads((root/"value_adds.json").read_text())
    if v.get("schema")!="lds.autonomous-operations.value-adds/1":
        errors.append("value-add schema drift")
    expected={
      "intent_to_execution_compiler","exception_autopilot","evidence_driven_completion_gate",
      "customer_dependency_automation","sla_deadline_guardian","autonomous_tool_model_router",
      "learning_optimization_loop","commercial_recovery_engine",
      "autonomous_change_impact_analyzer","global_kill_switch_circuit_breaker"
    }
    if set(v.get("value_adds",{}).keys())!=expected:
        errors.append("value-add set incomplete")

if (root/"governance_closure.json").exists():
    g=json.loads((root/"governance_closure.json").read_text())
    if g.get("schema")!="lds.autonomous-operations.governance-closure/1":
        errors.append("governance closure schema drift")
    expected={
      "policy_as_code","identity_credential_permission_broker",
      "software_supply_chain_provenance_guard","continuous_resilience_chaos_verification",
      "customer_portability_exit_guarantee","autonomous_business_health_governor"
    }
    if set(g.get("layers",{}).keys())!=expected:
        errors.append("governance closure layer set incomplete")
    inv=" ".join(g.get("invariants",[]))
    for token in [
      "Unknown policy or authority state fails closed",
      "Agent access is least privilege",
      "Release claims require immutable provenance",
      "Chaos and resilience verification is non-production",
      "Customer portability composes the existing Handover & Exit Package",
      "Production deployment, destructive production data action and privilege widening remain human-only"
    ]:
        if token not in inv: errors.append(f"missing governance invariant {token}")

if errors:
    print("LDS Autonomous Operations Layer: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Autonomous Operations Layer: PASS")
