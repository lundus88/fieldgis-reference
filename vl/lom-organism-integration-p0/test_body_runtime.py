from pathlib import Path

from organism import ORGANS, SensorySignal, load_registry
from body_runtime import BodyRuntime

HERE = Path(__file__).resolve().parent
REGISTRY = load_registry(HERE / "organ-registry.json")
NOW = 2_000_000_000


def healthy_probes(*, degraded: str | None = None, missing: str | None = None):
    probes = {}
    for organ in sorted(ORGANS):
        if organ == missing:
            continue

        def make_probe(name):
            def probe():
                return {
                    "organ": name,
                    "status": "DEGRADED" if name == degraded else "HEALTHY",
                    "observed_at_epoch": NOW - 5,
                    "evidence_refs": [f"evidence:{name}"],
                }
            return probe

        probes[organ] = make_probe(organ)
    return probes


def signal(**overrides):
    data = dict(
        signal_id="sig-runtime-0001",
        source_organ="eyes",
        project_id="ebkl",
        signal_type="HEALTH",
        severity="LOW",
        observed_at_epoch=NOW - 5,
        expires_at_epoch=NOW + 300,
        evidence_refs=("evidence:signal",),
        requested_action=None,
        production=False,
        reversible=True,
        risk="LOW",
    )
    data.update(overrides)
    return SensorySignal(**data)


def recorder(events):
    def record(envelope):
        events.append(envelope)
        return {"evidence_id": f"runtime-evidence-{len(events)}"}
    return record


def learner(items):
    def learn(proposal):
        items.append(proposal)
        return {
            "proposal_only": True,
            "authority_change_applied": False,
            "learning_id": f"learning-{len(items)}",
        }
    return learn


def executor(items, *, production_locked=True):
    def execute(request):
        items.append(request)
        return {
            "decision": "ALLOW",
            "production_locked": production_locked,
            "action_digest": "sha256:" + "a" * 64,
        }
    return execute


def test_healthy_body_monitor_cycle_records_preflight_and_final():
    events = []
    runtime = BodyRuntime(
        REGISTRY,
        organ_probes=healthy_probes(),
        evidence_recorder=recorder(events),
    )
    result = runtime.cycle(now_epoch=NOW, max_age_seconds=300, signals=[signal()])
    assert result["status"] == "MONITOR"
    assert result["body_status"] == "HEALTHY"
    assert len(events) == 2
    assert events[0]["phase"] == "PREFLIGHT"
    assert events[1]["phase"] == "FINAL"


def test_low_risk_regression_reaches_existing_hands_boundary_only_as_prepare_pr():
    events = []
    actions = []
    learning = []
    runtime = BodyRuntime(
        REGISTRY,
        organ_probes=healthy_probes(),
        bounded_executor=executor(actions),
        evidence_recorder=recorder(events),
        learning_sink=learner(learning),
    )
    result = runtime.cycle(
        now_epoch=NOW,
        max_age_seconds=300,
        signals=[signal(
            signal_type="REGRESSION",
            severity="MEDIUM",
            requested_action="NON_PROD_CODE",
        )],
    )
    assert result["status"] == "PREPARED"
    assert len(actions) == 1
    assert actions[0]["max_authority"] == "PREPARE_PR"
    assert actions[0]["production"] is False
    assert actions[0]["production_locked"] is True
    assert len(learning) == 1
    assert learning[0]["proposal_only"] is True


def test_missing_hands_probe_holds_before_executor():
    events = []
    actions = []
    runtime = BodyRuntime(
        REGISTRY,
        organ_probes=healthy_probes(missing="hands"),
        bounded_executor=executor(actions),
        evidence_recorder=recorder(events),
        learning_sink=learner([]),
    )
    result = runtime.cycle(
        now_epoch=NOW,
        max_age_seconds=300,
        signals=[signal(signal_type="REGRESSION", requested_action="NON_PROD_CODE")],
    )
    assert result["status"] == "HOLD"
    assert result["reason"] == "HOMEOSTASIS_BLOCK"
    assert actions == []


def test_degraded_body_can_monitor_but_cannot_delegate_bounded_action():
    events = []
    actions = []
    runtime = BodyRuntime(
        REGISTRY,
        organ_probes=healthy_probes(degraded="memory"),
        bounded_executor=executor(actions),
        evidence_recorder=recorder(events),
        learning_sink=learner([]),
    )
    result = runtime.cycle(
        now_epoch=NOW,
        max_age_seconds=300,
        signals=[signal(signal_type="REGRESSION", requested_action="NON_PROD_CODE")],
    )
    assert result["status"] == "HOLD"
    assert result["reason"] == "BODY_DEGRADED_EXECUTION_BLOCKED"
    assert actions == []


def test_production_signal_never_reaches_executor_and_prepares_human_package():
    events = []
    actions = []
    reviews = []

    def voice(package):
        reviews.append(package)
        return {"package_id": "human-review-1"}

    runtime = BodyRuntime(
        REGISTRY,
        organ_probes=healthy_probes(),
        bounded_executor=executor(actions),
        evidence_recorder=recorder(events),
        learning_sink=learner([]),
        human_review_sink=voice,
    )
    result = runtime.cycle(
        now_epoch=NOW,
        max_age_seconds=300,
        signals=[signal(
            signal_type="WORK_READY",
            requested_action="PRODUCTION_DEPLOY",
            production=True,
        )],
    )
    assert result["status"] == "HUMAN_REVIEW"
    assert actions == []
    assert len(reviews) == 1
    assert reviews[0]["authority"] == "HUMAN_ONLY"


def test_executor_must_prove_production_is_locked():
    events = []
    actions = []
    runtime = BodyRuntime(
        REGISTRY,
        organ_probes=healthy_probes(),
        bounded_executor=executor(actions, production_locked=False),
        evidence_recorder=recorder(events),
        learning_sink=learner([]),
    )
    result = runtime.cycle(
        now_epoch=NOW,
        max_age_seconds=300,
        signals=[signal(signal_type="REGRESSION", requested_action="NON_PROD_CODE")],
    )
    assert result["status"] == "HOLD"
    assert result["reason"] == "EXECUTOR_PRODUCTION_BOUNDARY_UNPROVEN"


def test_missing_evidence_recorder_blocks_before_executor():
    actions = []
    runtime = BodyRuntime(
        REGISTRY,
        organ_probes=healthy_probes(),
        bounded_executor=executor(actions),
        learning_sink=learner([]),
    )
    result = runtime.cycle(
        now_epoch=NOW,
        max_age_seconds=300,
        signals=[signal(signal_type="REGRESSION", requested_action="NON_PROD_CODE")],
    )
    assert result["status"] == "HOLD"
    assert result["reason"] == "EVIDENCE_RECORDER_UNAVAILABLE"
    assert actions == []


def test_missing_learning_sink_blocks_before_executor():
    events = []
    actions = []
    runtime = BodyRuntime(
        REGISTRY,
        organ_probes=healthy_probes(),
        bounded_executor=executor(actions),
        evidence_recorder=recorder(events),
    )
    result = runtime.cycle(
        now_epoch=NOW,
        max_age_seconds=300,
        signals=[signal(signal_type="REGRESSION", requested_action="NON_PROD_CODE")],
    )
    assert result["status"] == "HOLD"
    assert result["reason"] == "LEARNING_SINK_UNAVAILABLE"
    assert actions == []


def test_duplicate_signal_id_fails_closed():
    events = []
    actions = []
    runtime = BodyRuntime(
        REGISTRY,
        organ_probes=healthy_probes(),
        bounded_executor=executor(actions),
        evidence_recorder=recorder(events),
        learning_sink=learner([]),
    )
    one = signal(signal_id="dup-1")
    two = signal(signal_id="dup-1", signal_type="REGRESSION")
    result = runtime.cycle(now_epoch=NOW, max_age_seconds=300, signals=[one, two])
    assert result["status"] == "HOLD"
    assert result["reason"] == "SIGNAL_INTAKE_BLOCK"
    assert actions == []


def test_signal_source_can_drive_ears_without_direct_external_authority():
    events = []
    runtime = BodyRuntime(
        REGISTRY,
        organ_probes=healthy_probes(),
        evidence_recorder=recorder(events),
        signal_source=lambda: [signal(signal_id="ear-1")],
    )
    result = runtime.cycle(now_epoch=NOW, max_age_seconds=300, signals=None)
    assert result["status"] == "MONITOR"
    assert result["routes"][0]["signal_id"] == "ear-1"


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
    print(f"PASS {len(tests)} LOM Organism Runtime P1 tests")
