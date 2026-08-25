#!/usr/bin/env python3
import argparse
import pathlib
import sys
import yaml


def load_manifest(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def all_gates_satisfied(data):
    required = data["certification"]["required_gates"]
    status = data["certification"].get("gate_status", {})
    accepted = {"passed", "approved"}
    missing = [gate for gate in required if status.get(gate) not in accepted]
    return missing


def validate_pending(data):
    if data.get("status") != "experimental":
        raise AssertionError("Pending certification must remain experimental")
    if data["certification"].get("state") != "pending":
        raise AssertionError("Certification must remain pending before all gates pass")
    if data["certification"].get("direct_activation_allowed") is not False:
        raise AssertionError("Direct activation must be disabled")


def validate_activation(data):
    missing = all_gates_satisfied(data)
    if missing:
        raise AssertionError("Activation blocked; missing gates: " + ", ".join(missing))
    if data["certification"].get("state") != "approved":
        raise AssertionError("All gates may pass, but certification.state must be approved")


def validate_rollback(data):
    target = data.get("activation", {}).get("rollback_status")
    if target != "experimental":
        raise AssertionError("Rollback target must be experimental")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--mode", choices=["pending", "activation", "rollback"], required=True)
    args = parser.parse_args()
    data = load_manifest(args.manifest)
    if args.mode == "pending":
        validate_pending(data)
    elif args.mode == "activation":
        validate_activation(data)
    else:
        validate_rollback(data)
    print(f"VL certification gate validation passed: {args.mode}")


if __name__ == "__main__":
    main()
