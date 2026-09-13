import json
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parent

spec = importlib.util.spec_from_file_location("task_runtime", ROOT / "task_runtime.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

policy = json.loads((ROOT / "runtime-policy.json").read_text())

class TransientError(Exception):
    error_class = "TRANSIENT_TOOL_ERROR"


def test_human_only_escalates():
    rt = mod.Runtime(policy)
    task = mod.Task("t1", "PRODUCTION_DEPLOYMENT", ["ev1"])
    assert rt.execute(task, lambda t: None) == mod.ESCALATED
    assert task.error_class == "HUMAN_ONLY_ACTION"


def test_unknown_authority_escalates():
    rt = mod.Runtime(policy)
    task = mod.Task("t2", "UNLISTED_ACTION", ["ev1"])
    assert rt.execute(task, lambda t: None) == mod.ESCALATED
    assert task.error_class == "UNKNOWN_AUTHORITY"


def test_missing_evidence_escalates():
    rt = mod.Runtime(policy)
    task = mod.Task("t3", "RUN_TEST", [])
    assert rt.execute(task, lambda t: None) == mod.ESCALATED
    assert task.error_class == "MISSING_REQUIRED_EVIDENCE"


def test_retry_safe_failure_retries_then_validates():
    rt = mod.Runtime(policy)
    task = mod.Task("t4", "RUN_TEST", ["ev1"])
    calls = {"n": 0}
    def execute(t):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TransientError("temporary")
        return {"ok": True}
    assert rt.execute(task, execute) == mod.VALIDATING
    assert calls["n"] == 2
    assert rt.validate(task, lambda t: True) == mod.COMPLETED


def test_high_risk_escalates_before_execution():
    rt = mod.Runtime(policy)
    task = mod.Task("t5", "RUN_STATIC_ANALYSIS", ["ev1"], risk_class="HIGH")
    assert rt.execute(task, lambda t: None) == mod.ESCALATED
    assert task.error_class == "RISK_THRESHOLD_EXCEEDED"


def test_validation_failure_escalates():
    rt = mod.Runtime(policy)
    task = mod.Task("t6", "GENERATE_NON_PRODUCTION_ARTIFACT", ["ev1"])
    assert rt.execute(task, lambda t: "artifact") == mod.VALIDATING
    assert rt.validate(task, lambda t: False) == mod.ESCALATED
    assert task.error_class == "VALIDATION_FAILED"
