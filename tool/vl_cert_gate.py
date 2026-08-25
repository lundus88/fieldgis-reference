#!/usr/bin/env python3
import argparse

ACCEPTED = {"passed", "approved"}


def parse_manifest(path: str):
    data = {
        "status": None,
        "cert_state": None,
        "direct_activation_allowed": None,
        "required_gates": [],
        "gate_status": {},
        "rollback_status": None,
    }
    section = None
    subsection = None
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(line) - len(line.lstrip(" "))
            if indent == 0 and ":" in stripped:
                key, value = stripped.split(":", 1)
                section = key
                subsection = None
                if key == "status":
                    data["status"] = value.strip()
                continue
            if section == "certification":
                if indent == 2 and stripped.startswith("state:"):
                    data["cert_state"] = stripped.split(":", 1)[1].strip()
                elif indent == 2 and stripped.startswith("direct_activation_allowed:"):
                    data["direct_activation_allowed"] = stripped.split(":", 1)[1].strip().lower() == "true"
                elif indent == 2 and stripped == "required_gates:":
                    subsection = "required_gates"
                elif indent == 2 and stripped == "gate_status:":
                    subsection = "gate_status"
                elif indent == 4 and subsection == "required_gates" and stripped.startswith("- "):
                    data["required_gates"].append(stripped[2:].strip())
                elif indent == 4 and subsection == "gate_status" and ":" in stripped:
                    key, value = stripped.split(":", 1)
                    data["gate_status"][key.strip()] = value.strip()
            elif section == "activation" and indent == 2 and stripped.startswith("rollback_status:"):
                data["rollback_status"] = stripped.split(":", 1)[1].strip()
    return data


def missing_gates(data):
    return [g for g in data["required_gates"] if data["gate_status"].get(g) not in ACCEPTED]


def validate_pending(data):
    assert data["status"] == "experimental", "Pending certification must remain experimental"
    assert data["cert_state"] == "pending", "Certification must remain pending"
    assert data["direct_activation_allowed"] is False, "Direct activation must be disabled"


def validate_activation(data):
    missing = missing_gates(data)
    assert not missing, "Activation blocked; missing gates: " + ", ".join(missing)
    assert data["cert_state"] == "approved", "certification.state must be approved"


def validate_rollback(data):
    assert data["rollback_status"] == "experimental", "Rollback target must be experimental"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--mode", choices=["pending", "activation", "rollback"], required=True)
    args = parser.parse_args()
    data = parse_manifest(args.manifest)
    {"pending": validate_pending, "activation": validate_activation, "rollback": validate_rollback}[args.mode](data)
    print(f"VL certification gate validation passed: {args.mode}")


if __name__ == "__main__":
    main()
