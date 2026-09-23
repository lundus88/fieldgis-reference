from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    declared = data.pop("manifest_digest")
    assert digest(data) == declared, "manifest digest mismatch"
    assert data["source_sha"] == args.expected_sha, "source SHA mismatch"
    assert data["target_environment"] == "development", "non-DEV target rejected"
    assert data["production_mutation"] is False, "production mutation must be false"
    assert data["verdict"] == "HOLD", "phase-one manifest must not fabricate PASS"
    assert len(data["results"]) == 3, "expected exactly three benchmark cases"
    assert all(x["status"] == "PASS" for x in data["results"]), "benchmark case failed"
    assert any(x["result"]["decision"] == "DENY" for x in data["results"]), "missing denial control"
    assert any(x["result"]["decision"] == "REQUIRE_CLARIFICATION" for x in data["results"]), "missing clarification control"
    assert any(x["result"]["decision"] == "ROUTE" for x in data["results"]), "missing positive route"
    print(json.dumps({"status": "PASS", "verdict": data["verdict"], "manifest_digest": declared}))


if __name__ == "__main__":
    main()
