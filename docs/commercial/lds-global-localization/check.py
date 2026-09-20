#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-global-localization")
errors=[]
for f in ["README.md","contract.json","engine.py","test_engine.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.global-localization/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain false")
    if d.get("automatic_legal_translation_authorized") is not False: errors.append("legal translation must remain false")
    text=" ".join(d.get("invariants",[]))
    for t in ["approved and versioned","must not be invented","does not authorize exchange-rate","fallback review","rights, price, scope or obligations","does not itself authorize"]:
        if t not in text: errors.append(f"missing invariant {t}")
if errors:
    print("LD Global Localization: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LD Global Localization: PASS")
