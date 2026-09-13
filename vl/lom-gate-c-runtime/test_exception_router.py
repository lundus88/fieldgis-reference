import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("exception_router", ROOT / "exception_router.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_human_only_routes_to_director():
    result = mod.route({"task_id": "a", "error_class": "HUMAN_ONLY_ACTION", "evidence": ["e1"]})
    assert result["destination"] == mod.DIRECTOR_QUEUE
    assert result["requires_human_attention"] is True


def test_missing_evidence_routes_to_evidence_queue():
    result = mod.route({"task_id": "b", "error_class": "MISSING_REQUIRED_EVIDENCE"})
    assert result["destination"] == mod.EVIDENCE_QUEUE
    assert result["requires_human_attention"] is False


def test_unknown_exception_fails_closed_to_director():
    result = mod.route({"task_id": "c", "error_class": "SOMETHING_NEW"})
    assert result["destination"] == mod.DIRECTOR_QUEUE
    assert result["requires_human_attention"] is True
