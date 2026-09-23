import json
from pathlib import Path

from ready_business_p3 import (
    evaluate_controlled_transaction_prereqs,
    create_revenue_readiness_packet,
    make_synthetic_readiness_fixture,
    assess_real_revenue_proof,
)

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/"generated-p3"
OUT.mkdir(exist_ok=True)

snapshot=json.loads((ROOT/"docs/commercial/LDS_ACTIVATION_SNAPSHOT.json").read_text())
prereq=evaluate_controlled_transaction_prereqs(snapshot)
packet=create_revenue_readiness_packet(
    prospect_ref="synthetic-prospect-001",
    project_id="LD-SYNTHETIC-P3-001",
)
fixture=make_synthetic_readiness_fixture(packet)
assessment=assess_real_revenue_proof(fixture,controlled_prereq_decision=prereq["decision"])

report={
    "schema":"ld.p3-ci-readiness-report/1",
    "current_controlled_transaction_prereq":prereq,
    "synthetic_assessment":assessment,
    "live_transaction_performed":False,
    "payment_transactions":0,
    "production_mutations":0,
    "real_customers":0,
    "real_revenue_proof":False,
    "activation_authorized":False,
}
(OUT/"p3-readiness-report.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
