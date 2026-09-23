import json
from pathlib import Path
from ready_business_p1 import create_client_project

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"generated-p1"
OUT.mkdir(exist_ok=True)

for p in (ROOT/"verticals").glob("*.json"):
    onboarding=json.loads(p.read_text())
    result=create_client_project(onboarding,"starter")
    if result["decision"]!="ALLOW":
        raise SystemExit(f"{p.name}: {result}")
    stem=p.stem
    (OUT/f"{stem}.preview.html").write_text(result["preview_html"])
    (OUT/f"{stem}.proposal.json").write_text(json.dumps(result["proposal"],indent=2)+"\n")
    (OUT/f"{stem}.quotation.json").write_text(json.dumps(result["quotation"],indent=2)+"\n")
    (OUT/f"{stem}.workspace.json").write_text(json.dumps(result["workspace"],indent=2)+"\n")
    print("generated-p1",stem,result["project_id"])
