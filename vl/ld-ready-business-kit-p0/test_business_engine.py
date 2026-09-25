import json
from pathlib import Path
from business_engine import validate_industry_pack, engine_manifest, CANONICAL_STATES

ROOT = Path(__file__).resolve().parent

def load_pack():
    return json.loads((ROOT / "industry-packs" / "property-broker.json").read_text())

def test_property_pack_validates():
    out = validate_industry_pack(load_pack())
    assert out["decision"] == "ALLOW"
    assert len(out["digest"]) == 64

def test_manifest_is_locked():
    out = engine_manifest(load_pack())
    assert out["decision"] == "ALLOW"
    assert out["production"] == "LOCKED"
    assert out["live_charging"] == "LOCKED"
    assert out["human_approval_required"] is True
    assert out["authority"]["production_deploy"] == "HUMAN_ONLY"

def test_canonical_lifecycle_present():
    assert CANONICAL_STATES[0] == "VISITOR"
    assert "PAYMENT_RECONCILED" in CANONICAL_STATES
    assert "CUSTOMER_ACCEPTED" in CANONICAL_STATES
    assert CANONICAL_STATES[-1] == "CLOSED"

def test_unknown_capability_fails_closed():
    pack = load_pack()
    pack["capabilities"].append("MAGIC_DATABASE_ACCESS")
    out = validate_industry_pack(pack)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "PACK_CAPABILITY_UNKNOWN"

def test_unknown_human_gate_fails_closed():
    pack = load_pack()
    pack["human_gates"].append("AUTO_APPROVE_EVERYTHING")
    out = validate_industry_pack(pack)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "PACK_HUMAN_GATE_UNKNOWN"

if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
    print(f"PASS {len(tests)} LD Business Engine v1 tests")
