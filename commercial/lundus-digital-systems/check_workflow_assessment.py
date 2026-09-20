#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("commercial/lundus-digital-systems")
errors=[]
for f in ["workflow-assessment.html","workflow-assessment-result.html","workflow-assessment-contract.json","assessment_engine.py","test_assessment_engine.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"workflow-assessment-contract.json").exists():
    d=json.loads((root/"workflow-assessment-contract.json").read_text())
    if d.get("schema")!="lds.workflow-assessment/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production activation must remain false")
    forbidden=set(d.get("forbidden_actions",[]))
    for x in ["auto_quotation","auto_pricing","auto_payment","auto_sale","auto_rejection_from_score_only"]:
        if x not in forbidden: errors.append(f"missing forbidden action {x}")
    ff=set(d.get("forbidden_free_output",[]))
    for x in ["full_system_architecture","source_code","binding_price","binding_delivery_date"]:
        if x not in ff: errors.append(f"missing free-output boundary {x}")
page=(root/"workflow-assessment.html").read_text() if (root/"workflow-assessment.html").exists() else ""
for x in ["problem_statement","current_workflow","desired_outcome","budget_band","Do not enter passwords"]:
    if x not in page: errors.append(f"assessment page missing {x}")
result=(root/"workflow-assessment-result.html").read_text() if (root/"workflow-assessment-result.html").exists() else ""
for x in ["Problem identified","Suggested direction","What happens next","no final architecture"]:
    if x not in result: errors.append(f"result page missing {x}")
if errors:
    print("LDS Workflow Assessment: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Workflow Assessment: PASS")
