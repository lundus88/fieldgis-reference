from dataclasses import dataclass, asdict
from typing import Dict, Tuple

HUMAN_ONLY_TARGETS = {
    'PROTECTED_MAIN_MERGE','PRODUCTION_RELEASE','PRODUCTION_DATA_MUTATION',
    'AUTHORITY_WIDENING','AUTH_SECURITY_POLICY_CHANGE','CUSTOMER_COMMITMENT',
    'BID_SUBMISSION','PRICING_COMMITMENT','CONTRACT_COMMITMENT',
    'FINANCIAL_COMMITMENT','DATA_DELETION'
}

ALLOWED_TARGETS = {
    'PROMPT','ROUTING','DOCUMENTATION','TEST_COVERAGE','NON_PROD_CODE',
    'NON_PROD_WORKFLOW','UI_NON_PROD','EVALUATION','OBSERVABILITY'
}

@dataclass(frozen=True)
class Observation:
    observation_id: str
    target: str
    evidence_state: str
    evidence_ref: str
    problem: str

@dataclass(frozen=True)
class CandidateImprovement:
    candidate_id: str
    target: str
    proposed_change: str
    risk: str
    reversible: bool
    production: bool

@dataclass(frozen=True)
class EvaluationResult:
    before_score: float
    after_score: float
    correctness_before: float
    correctness_after: float
    safety_before: float
    safety_after: float
    regression_passed: bool
    independently_validated: bool

    @property
    def delta(self) -> float:
        return round(self.after_score - self.before_score, 4)

@dataclass(frozen=True)
class ImprovementRecord:
    observation_id: str
    candidate_id: str
    target: str
    evidence_ref: str
    before_score: float
    after_score: float
    delta: float
    regression_passed: bool
    independently_validated: bool
    disposition: str

class ImprovementLedger:
    def __init__(self): self._records: Dict[str, ImprovementRecord] = {}
    def append(self, record: ImprovementRecord):
        key = f'{record.observation_id}:{record.candidate_id}'
        if key in self._records: raise ValueError('DUPLICATE_IMPROVEMENT_RECORD')
        self._records[key] = record
    def all(self): return list(self._records.values())

class SelfImprovementRuntime:
    def observe(self, observation: Observation) -> str:
        if observation.evidence_state != 'READY':
            raise ValueError('EVIDENCE_NOT_READY')
        if not observation.evidence_ref.strip():
            raise ValueError('EVIDENCE_REFERENCE_REQUIRED')
        if observation.target in HUMAN_ONLY_TARGETS:
            return 'ESCALATE'
        if observation.target not in ALLOWED_TARGETS:
            return 'HOLD'
        return 'DIAGNOSE'

    def stage(self, candidate: CandidateImprovement) -> str:
        if candidate.target in HUMAN_ONLY_TARGETS:
            return 'ESCALATE'
        if candidate.target not in ALLOWED_TARGETS:
            return 'HOLD'
        if candidate.production:
            return 'ESCALATE'
        if candidate.risk not in {'LOW','MEDIUM','HIGH'}:
            return 'HOLD'
        if candidate.risk == 'HIGH':
            return 'ESCALATE'
        if not candidate.reversible:
            return 'HOLD'
        return 'SANDBOX'

    def compare(self, result: EvaluationResult) -> str:
        for value in (
            result.before_score, result.after_score,
            result.correctness_before, result.correctness_after,
            result.safety_before, result.safety_after,
        ):
            if value < 0 or value > 1:
                raise ValueError('SCORE_OUT_OF_RANGE')
        if not result.regression_passed:
            return 'REJECT'
        if not result.independently_validated:
            return 'HOLD'
        if result.correctness_after < result.correctness_before:
            return 'REJECT'
        if result.safety_after < result.safety_before:
            return 'REJECT'
        if result.after_score <= result.before_score:
            return 'REJECT'
        return 'PREPARE_PR'

    def record(self, ledger: ImprovementLedger, observation: Observation,
               candidate: CandidateImprovement, result: EvaluationResult,
               disposition: str) -> ImprovementRecord:
        record = ImprovementRecord(
            observation_id=observation.observation_id,
            candidate_id=candidate.candidate_id,
            target=candidate.target,
            evidence_ref=observation.evidence_ref,
            before_score=result.before_score,
            after_score=result.after_score,
            delta=result.delta,
            regression_passed=result.regression_passed,
            independently_validated=result.independently_validated,
            disposition=disposition,
        )
        ledger.append(record)
        return record

    def apply_to_protected_main(self, *args, **kwargs):
        raise PermissionError('SELF_APPROVAL_FORBIDDEN')

    def deploy_production(self, *args, **kwargs):
        raise PermissionError('PRODUCTION_RELEASE_REQUIRES_HUMAN')
