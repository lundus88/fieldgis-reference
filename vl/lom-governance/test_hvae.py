#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import sys

MODULE = Path(__file__).with_name("hvae.py")
spec = importlib.util.spec_from_file_location("hvae", MODULE)
hvae = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = hvae
spec.loader.exec_module(hvae)

def c(**kw):
    base = dict(
        name="candidate",
        evidence_present=True,
        duplicate_capability_exists=False,
        external_integration_only=False,
        domain_subset=False,
        reusable_pattern=False,
        cross_domain_shared_logic=False,
        distinct_domain_rules=False,
        distinct_lifecycle=False,
        distinct_data=False,
        runtime_change=False,
        rollback_defined=True,
        owner_identified=True,
        architecture_target_identified=True,
        risk_assessed=True,
    )
    base.update(kw)
    return hvae.Candidate(**base)

assert hvae.evaluate(c(duplicate_capability_exists=True)).disposition == "UPGRADE_EXISTING_CAPABILITY"
assert hvae.evaluate(c(external_integration_only=True)).disposition == "ADD_ADAPTER"
assert hvae.evaluate(c(domain_subset=True)).disposition == "ADD_DOMAIN_CAPABILITY"
assert hvae.evaluate(c(reusable_pattern=True)).disposition == "ADD_TEMPLATE"
assert hvae.evaluate(c(cross_domain_shared_logic=True)).disposition == "ADD_SHARED_ENGINE"
assert hvae.evaluate(c(distinct_domain_rules=True, distinct_lifecycle=True, distinct_data=True)).disposition == "ADD_NEW_MODULE"
assert hvae.evaluate(c(evidence_present=False)).disposition == "REJECT"
assert hvae.evaluate(c(runtime_change=True, rollback_defined=False)).disposition == "REJECT"
assert hvae.evaluate(c()).disposition == "KNOWLEDGE_ONLY"

print("LOM_HVAE_TESTS=PASS")
