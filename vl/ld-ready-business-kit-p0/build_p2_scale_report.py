import json
from pathlib import Path

from ready_business_p2 import simulate_ten_customers

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"generated-p2"
OUT.mkdir(exist_ok=True)

fixtures=[
    json.loads((ROOT/"verticals"/"cafe.json").read_text()),
    json.loads((ROOT/"verticals"/"homestay.json").read_text()),
    json.loads((ROOT/"verticals"/"tutor.json").read_text()),
]

report=simulate_ten_customers(fixtures,daily_limit=3,concurrent_limit=1)
if report["decision"]!="ALLOW":
    raise SystemExit(report)

(OUT/"synthetic-10-client-report.json").write_text(json.dumps(report,indent=2)+"\n")

summary=[
    "# Synthetic 10-Client Scale Report",
    "",
    "This report is synthetic only. It is not customer or revenue evidence.",
    "",
    f"- Customer fixtures: {report['customer_count']}",
    f"- Unique projects: {report['unique_project_ids']}",
    f"- Unique tenants: {report['unique_tenant_ids']}",
    f"- Assumed daily limit: {report['capacity_plan']['daily_limit']}",
    f"- Assumed concurrent limit: {report['capacity_plan']['concurrent_limit']}",
    f"- Estimated delivery days under fixture limits: {report['capacity_plan']['estimated_delivery_days']}",
    f"- Bottlenecks: {', '.join(report['capacity_plan']['bottlenecks']) or 'NONE'}",
    "- Live payments: 0",
    "- Production deployments: 0",
    "- Activation authorized: NO",
]
(OUT/"synthetic-10-client-summary.md").write_text("\n".join(summary)+"\n")
print("generated P2 synthetic 10-client report")
