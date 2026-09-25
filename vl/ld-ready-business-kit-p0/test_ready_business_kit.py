import json
from pathlib import Path
from ready_business_kit import validate_onboarding, render_preview

ROOT=Path(__file__).resolve().parent

def load(name):
    return json.loads((ROOT/"verticals"/name).read_text())

def test_four_verticals_render():
    for name in ["cafe.json","homestay.json","tutor.json","property.json"]:
        data=load(name)
        v=validate_onboarding(data)
        assert v["decision"]=="ALLOW"
        out=render_preview(data)
        assert out["decision"]=="ALLOW"
        assert "<!doctype html>" in out["html"].lower()
        assert out["manifest"]["payment"]=="DISABLED"
        assert out["manifest"]["production"]=="LOCKED"
        assert out["manifest"]["human_approval_required"] is True

def test_missing_required_holds():
    d=load("cafe.json")
    d.pop("whatsapp")
    r=validate_onboarding(d)
    assert r["decision"]=="HOLD"
    assert "whatsapp" in r["missing"]

def test_bad_vertical_holds():
    d=load("cafe.json")
    d["vertical"]="unknown"
    assert validate_onboarding(d)["reason"]=="UNSUPPORTED_VERTICAL"

def test_empty_vertical_payload_holds():
    d=load("homestay.json")
    d["rooms"]=[]
    r=validate_onboarding(d)
    assert r["decision"]=="HOLD"

def test_manifest_is_deterministic():
    d=load("tutor.json")
    a=render_preview(d)["manifest"]
    b=render_preview(d)["manifest"]
    assert a==b

if __name__=="__main__":
    tests=[v for k,v in globals().items() if k.startswith("test_") and callable(v)]
    for t in tests:t()
    print(f"PASS {len(tests)} LD Ready Business Kit P0 tests")
