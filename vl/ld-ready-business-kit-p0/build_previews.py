import json
from pathlib import Path
from ready_business_kit import render_preview

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"generated"
OUT.mkdir(exist_ok=True)

for p in (ROOT/"verticals").glob("*.json"):
    data=json.loads(p.read_text())
    result=render_preview(data)
    if result["decision"]!="ALLOW":
        raise SystemExit(f"{p.name}: {result}")
    (OUT/f"{p.stem}.html").write_text(result["html"])
    (OUT/f"{p.stem}.manifest.json").write_text(json.dumps(result["manifest"],indent=2)+"\n")
    print("generated",p.stem)
