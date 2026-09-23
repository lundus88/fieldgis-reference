from dataclasses import dataclass, field
from typing import List, Optional, Tuple

HUMAN_ONLY_TARGETS = {
    "PROTECTED_MAIN_MERGE",
    "PRODUCTION_RELEASE",
    "PRODUCTION_DATA_MUTATION",
    "AUTHORITY_WIDENING",
    "AUTH_SECURITY_POLICY_CHANGE",
    "CUSTOMER_COMMITMENT",
    "BID_SUBMISSION",
    "PRICING_COMMITMENT",
    "CONTRACT_COMMITMENT",
    "FINANCIAL_COMMITMENT",
    "DATA_DELETION",
}

ALLOWED_TARGETS = {
    "PROMPT",
    "ROUTING",
    "DOCUMENTATION",
    "TEST_COVERAGE",
    "NON_PROD_CODE",
    "NON_PROD_WORKFLOW",
    "UI_NON_PROD",
    "EVALUATION",
    "OBSERVABILITY",
}

TASK_STATES = (
    "DISCOVERED",
    "QUALIFIED",
    "PLANNED",
    "SANDBOX",
    "TESTED",
    "SCORED",
    "REMEDIATED",
    "CERTIFIED",
    "PREPARE_PR",
    "HOLD",
    "REJECT",
    "ESCALATE",
)

TRIGGER_TYPES = {"MANUAL", "SCHEDULE", "EVENT", "CI_FAILURE", "OBSERVABILITY_ALERT"}


@dataclass(frozen=True)
class Budget:
    max_cost_usd: float
    max_elapsed_seconds: int
    max_retries: int
    max_tool_calls: int

    def valid(self) -> bool:
        return (
            self.max_cost_usd >= 0
            and self.max_elapsed_seconds > 0
            and self.max_retries >= 0
            and self.max_tool_calls > 0
        )


@dataclass(frozen=True)
class Usage:
    cost_usd: float
    elapsed_seconds: int
    retries: int
    tool_calls: int

    def valid(self) -> bool:
        return (
            self.cost_usd >= 0
            and self.elapsed_seconds >= 0
            and self.retries >= 0
            and self.tool_calls >= 0
        )

    def within(self, budget: Budget) -> bool:
        return (
            self.valid()
            and self.cost_usd <= budget.max_cost_usd
            and self.elapsed_seconds <= budget.max_elapsed_seconds
            and self.retries <= budget.max_retries
            and self.tool_calls <= budget.max_tool_calls
        )


@dataclass(frozen=True)
class Trigger:
    trigger_id: str
    trigger_type: str
    source_ref: str
    evidence_ref: str

    def valid(self) -> bool:
        return (
            bool(self.trigger_id.strip())
            and self.trigger_type in TRIGGER_TYPES
            and bool(self.source_ref.strip())
            and bool(self.evidence_ref.strip())
        )


@dataclass(frozen=True)
class Evaluation:
    correctness: float
    safety: float
    regression: float
    ux: float = 1.0
    performance: float = 1.0
    evidence_complete: bool = True

    def values(self) -> Tuple[float, ...]:
        return (
            self.correctness,
            self.safety,
            self.regression,
            self.ux,
            self.performance,
        )

    def valid(self) -> bool:
        return all(0.0 <= v <= 1.0 for v in self.values())

    def weighted_score(self) -> float:
        return round(
            (0.35 * self.correctness)
            + (0.30 * self.safety)
            + (0.20 * self.regression)
            + (0.075 * self.ux)
            + (0.075 * self.performance),
            4,
        )


@dataclass
class ImprovementTask:
    task_id: str
    target: str
    risk: str
    reversible: bool
    production: bool
    evidence_ref: str
    objective: str
    builder_id: str
    certifier_id: str
    budget: Budget
    trigger: Trigger
    state: str = field(default="DISCOVERED", init=False)
    attempts: int = field(default=0, init=False)
    history: List[str] = field(default_factory=lambda: ["DISCOVERED"], init=False)
    reason: str = field(default="CREATED", init=False)

    def transition(self, new_state: str, reason: str) -> None:
        if new_state not in TASK_STATES:
            raise ValueError("UNKNOWN_TASK_STATE")
        self.state = new_state
        self.reason = reason
        self.history.append(new_state)


class CAIE:
    """Bounded Continuous Autonomous Improvement Engine.

    Autonomous ceiling: PREPARE_PR.
    Protected-main merge and Production remain HUMAN_ONLY.
    """

    def __init__(
        self,
        min_correctness: float = 0.90,
        min_safety: float = 0.95,
        min_regression: float = 0.95,
        min_total_score: float = 0.92,
        max_remediation_attempts: int = 2,
    ) -> None:
        self.min_correctness = min_correctness
        self.min_safety = min_safety
        self.min_regression = min_regression
        self.min_total_score = min_total_score
        self.max_remediation_attempts = max_remediation_attempts

    def qualify(self, task: ImprovementTask) -> str:
        if not task.task_id.strip() or not task.objective.strip():
            task.transition("HOLD", "IDENTITY_OR_OBJECTIVE_REQUIRED")
            return task.state
        if not task.evidence_ref.strip():
            task.transition("HOLD", "EVIDENCE_REFERENCE_REQUIRED")
            return task.state
        if not task.trigger.valid():
            task.transition("HOLD", "TRIGGER_EVIDENCE_INVALID")
            return task.state
        if not task.budget.valid():
            task.transition("HOLD", "BUDGET_INVALID")
            return task.state
        if task.target in HUMAN_ONLY_TARGETS:
            task.transition("ESCALATE", "HUMAN_ONLY_TARGET")
            return task.state
        if task.target not in ALLOWED_TARGETS:
            task.transition("HOLD", "UNKNOWN_TARGET")
            return task.state
        if task.production:
            task.transition("ESCALATE", "PRODUCTION_BOUNDARY")
            return task.state
        if task.risk not in {"LOW", "MEDIUM", "HIGH"}:
            task.transition("HOLD", "UNKNOWN_RISK")
            return task.state
        if task.risk == "HIGH":
            task.transition("ESCALATE", "HIGH_RISK")
            return task.state
        if not task.reversible:
            task.transition("HOLD", "REVERSIBILITY_REQUIRED")
            return task.state
        if not task.builder_id.strip() or not task.certifier_id.strip():
            task.transition("HOLD", "ROLE_IDENTITY_REQUIRED")
            return task.state
        if task.builder_id == task.certifier_id:
            task.transition("HOLD", "BUILDER_SELF_CERTIFICATION_FORBIDDEN")
            return task.state
        task.transition("QUALIFIED", "BOUNDARY_CHECKS_PASSED")
        return task.state

    def plan(self, task: ImprovementTask) -> str:
        if task.state != "QUALIFIED":
            task.transition("HOLD", "PLAN_REQUIRES_QUALIFIED")
            return task.state
        task.transition("PLANNED", "BOUNDED_PLAN_READY")
        return task.state

    def enter_sandbox(self, task: ImprovementTask, isolated: bool) -> str:
        if task.state != "PLANNED":
            task.transition("HOLD", "SANDBOX_REQUIRES_PLANNED")
            return task.state
        if not isolated:
            task.transition("HOLD", "ISOLATED_EXECUTION_REQUIRED")
            return task.state
        task.transition("SANDBOX", "ISOLATED_EXECUTION_CONFIRMED")
        return task.state

    def record_test(self, task: ImprovementTask, tests_passed: bool) -> str:
        if task.state not in {"SANDBOX", "REMEDIATED"}:
            task.transition("HOLD", "TEST_REQUIRES_SANDBOX_OR_REMEDIATED")
            return task.state
        if not tests_passed:
            if task.attempts < self.max_remediation_attempts:
                task.attempts += 1
                task.transition("REMEDIATED", "TEST_FAILED_REMEDIATE")
            else:
                task.transition("REJECT", "TEST_FAILED_REMEDIATION_EXHAUSTED")
            return task.state
        task.transition("TESTED", "DETERMINISTIC_TESTS_PASSED")
        return task.state

    def score(
        self,
        task: ImprovementTask,
        evaluation: Evaluation,
        baseline: Optional[Evaluation],
        usage: Usage,
    ) -> str:
        if task.state != "TESTED":
            task.transition("HOLD", "SCORING_REQUIRES_TESTED")
            return task.state
        if not evaluation.evidence_complete:
            task.transition("HOLD", "EVALUATION_EVIDENCE_INCOMPLETE")
            return task.state
        if not evaluation.valid():
            task.transition("HOLD", "EVALUATION_SCORE_INVALID")
            return task.state
        if not usage.valid():
            task.transition("HOLD", "USAGE_EVIDENCE_INVALID")
            return task.state
        if not usage.within(task.budget):
            task.transition("REJECT", "BUDGET_OVERRUN")
            return task.state
        if baseline is None:
            task.transition("HOLD", "BASELINE_EVIDENCE_REQUIRED")
            return task.state
        if not baseline.valid() or not baseline.evidence_complete:
            task.transition("HOLD", "BASELINE_EVIDENCE_INVALID")
            return task.state
        if (
            evaluation.correctness < baseline.correctness
            or evaluation.safety < baseline.safety
            or evaluation.regression < baseline.regression
        ):
            task.transition("REJECT", "QUALITY_REGRESSION")
            return task.state
        if evaluation.correctness < self.min_correctness:
            task.transition("REJECT", "CORRECTNESS_BELOW_THRESHOLD")
            return task.state
        if evaluation.safety < self.min_safety:
            task.transition("REJECT", "SAFETY_BELOW_THRESHOLD")
            return task.state
        if evaluation.regression < self.min_regression:
            task.transition("REJECT", "REGRESSION_BELOW_THRESHOLD")
            return task.state
        if evaluation.weighted_score() < self.min_total_score:
            task.transition("REJECT", "TOTAL_SCORE_BELOW_THRESHOLD")
            return task.state
        task.transition("SCORED", "QUALITY_THRESHOLDS_PASSED")
        return task.state

    def certify(
        self,
        task: ImprovementTask,
        independent_validation: bool,
        evidence_consistent: bool,
    ) -> str:
        if task.state != "SCORED":
            task.transition("HOLD", "CERTIFICATION_REQUIRES_SCORED")
            return task.state
        if task.builder_id == task.certifier_id:
            task.transition("HOLD", "BUILDER_SELF_CERTIFICATION_FORBIDDEN")
            return task.state
        if not independent_validation:
            task.transition("HOLD", "INDEPENDENT_VALIDATION_REQUIRED")
            return task.state
        if not evidence_consistent:
            task.transition("HOLD", "EVIDENCE_CONTRADICTION")
            return task.state
        task.transition("CERTIFIED", "INDEPENDENT_VALIDATION_PASSED")
        return task.state

    def prepare_pr(self, task: ImprovementTask) -> str:
        if task.state != "CERTIFIED":
            task.transition("HOLD", "PREPARE_PR_REQUIRES_CERTIFIED")
            return task.state
        required = ["DISCOVERED", "QUALIFIED", "PLANNED", "SANDBOX", "TESTED", "SCORED", "CERTIFIED"]
        cursor = 0
        for state in task.history:
            if cursor < len(required) and state == required[cursor]:
                cursor += 1
        if cursor != len(required):
            task.transition("HOLD", "CERTIFICATION_LINEAGE_INCOMPLETE")
            return task.state
        task.transition("PREPARE_PR", "AUTONOMOUS_CEILING_REACHED")
        return task.state

    def merge_protected_main(self) -> None:
        raise PermissionError("HUMAN_APPROVAL_REQUIRED")

    def deploy_production(self) -> None:
        raise PermissionError("HUMAN_APPROVAL_REQUIRED")


def run_to_prepare_pr(
    task: ImprovementTask,
    evaluation: Evaluation,
    baseline: Evaluation,
    usage: Usage,
    tests_passed: bool = True,
    isolated: bool = True,
    independent_validation: bool = True,
    evidence_consistent: bool = True,
) -> ImprovementTask:
    engine = CAIE()
    if engine.qualify(task) != "QUALIFIED":
        return task
    if engine.plan(task) != "PLANNED":
        return task
    if engine.enter_sandbox(task, isolated=isolated) != "SANDBOX":
        return task
    if engine.record_test(task, tests_passed=tests_passed) != "TESTED":
        return task
    if engine.score(task, evaluation, baseline, usage) != "SCORED":
        return task
    if engine.certify(task, independent_validation, evidence_consistent) != "CERTIFIED":
        return task
    engine.prepare_pr(task)
    return task
