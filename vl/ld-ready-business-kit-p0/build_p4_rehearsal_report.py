import json
from pathlib import Path

from ready_business_p4 import (
    evaluate_cutover_preflight,
    build_customer_zero_rehearsal,
    build_future_live_evidence_manifest,
    kill_switch_matrix,
)

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/"generated-p4"
OUT.mkdir(exist_ok=True)

snapshot=json.loads((ROOT/"docs/commercial/LDS_ACTIVATION_SNAPSHOT.json").read_text())
preflight=evaluate_cutover_preflight(
    snapshot,
    external_gates={
        "DEDICATED_BUSINESS_PHONE":"IN_PROGRESS",
        "COMPANY_ACCOUNT":"IN_PROGRESS",
    },
)
rollback_contract={
    "candidate_deployment_ref":"synthetic:candidate",
    "known_good_deployment_ref":"synthetic:known-good",
    "lead_intake_disable_ref":"synthetic:lead-off",
    "checkout_disable_ref":"synthetic:checkout-off",
    "billing_disable_ref":"synthetic:billing-off",
    "incident_path_ref":"synthetic:incident",
    "rollback_procedure_ref":"synthetic:rollback",
}
report={
    "schema":"ld.p4-ci-rehearsal-report/1",
    "preflight":preflight,
    "customer_zero":build_customer_zero_rehearsal(
        preflight=preflight,
        rollback_contract=rollback_contract,
    ),
    "kill_switch_matrix":kill_switch_matrix(),
    "future_evidence_template":build_future_live_evidence_manifest(),
    "live_transaction_performed":False,
    "payment_transactions":0,
    "production_mutations":0,
    "real_customers":0,
    "public_launch_authorized":False,
}
(OUT/"p4-rehearsal-report.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
