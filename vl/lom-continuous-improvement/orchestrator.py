from dataclasses import dataclass
from typing import Iterable, List, Tuple

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

READY_EVIDENCE = {'READY'}

@dataclass(frozen=True)
class ImprovementSignal:
    signal_id: str
    target: str
    evidence_state: str
    evidence_ref: str
    problem: str
    impact: float
    confidence: float
    risk: str
    reversible: bool
    production: bool

@dataclass(frozen=True)
class CandidateDecision:
    signal_id: str
    target: str
    priority: float
    disposition: str
    reason: str

class ContinuousImprovementOrchestrator:
    def qualify(self, signal: ImprovementSignal) -> CandidateDecision:
        if signal.evidence_state not in READY_EVIDENCE:
            return CandidateDecision(signal.signal_id, signal.target, 0.0, 'HOLD', 'EVIDENCE_NOT_READY')
        if not signal.evidence_ref.strip():
            return CandidateDecision(signal.signal_id, signal.target, 0.0, 'HOLD', 'EVIDENCE_REFERENCE_REQUIRED')
        if signal.target in HUMAN_ONLY_TARGETS:
            return CandidateDecision(signal.signal_id, signal.target, 0.0, 'ESCALATE', 'HUMAN_ONLY_TARGET')
        if signal.target not in ALLOWED_TARGETS:
            return CandidateDecision(signal.signal_id, signal.target, 0.0, 'HOLD', 'UNKNOWN_TARGET')
        if signal.production:
            return CandidateDecision(signal.signal_id, signal.target, 0.0, 'ESCALATE', 'PRODUCTION_BOUNDARY')
        if signal.risk not in {'LOW','MEDIUM','HIGH'}:
            return CandidateDecision(signal.signal_id, signal.target, 0.0, 'HOLD', 'UNKNOWN_RISK')
        if signal.risk == 'HIGH':
            return CandidateDecision(signal.signal_id, signal.target, 0.0, 'ESCALATE', 'HIGH_RISK')
        if not signal.reversible:
            return CandidateDecision(signal.signal_id, signal.target, 0.0, 'HOLD', 'REVERSIBILITY_REQUIRED')
        for value in (signal.impact, signal.confidence):
            if value < 0 or value > 1:
                return CandidateDecision(signal.signal_id, signal.target, 0.0, 'HOLD', 'SCORE_OUT_OF_RANGE')
        risk_penalty = 0.05 if signal.risk == 'MEDIUM' else 0.0
        priority = round((0.6 * signal.impact) + (0.4 * signal.confidence) - risk_penalty, 4)
        return CandidateDecision(signal.signal_id, signal.target, priority, 'QUALIFIED', 'READY_FOR_PRIORITIZATION')

    def prioritize(self, signals: Iterable[ImprovementSignal]) -> Tuple[List[CandidateDecision], List[CandidateDecision]]:
        qualified: List[CandidateDecision] = []
        blocked: List[CandidateDecision] = []
        for signal in signals:
            decision = self.qualify(signal)
            if decision.disposition == 'QUALIFIED':
                qualified.append(decision)
            else:
                blocked.append(decision)
        qualified.sort(key=lambda item: (-item.priority, item.signal_id))
        return qualified, blocked

    def next_action(self, decision: CandidateDecision) -> str:
        if decision.disposition == 'QUALIFIED':
            return 'STAGE_IN_SANDBOX'
        if decision.disposition == 'ESCALATE':
            return 'HUMAN_REVIEW'
        return 'NO_ACTION'

    def finalize_validation(self, regression_passed: bool, independently_validated: bool,
                            correctness_regressed: bool, safety_regressed: bool,
                            measurable_improvement: bool) -> str:
        if not regression_passed:
            return 'REJECT'
        if not independently_validated:
            return 'HOLD'
        if correctness_regressed or safety_regressed:
            return 'REJECT'
        if not measurable_improvement:
            return 'REJECT'
        return 'PREPARE_PR'

    def merge_protected_main(self):
        raise PermissionError('HUMAN_APPROVAL_REQUIRED')

    def deploy_production(self):
        raise PermissionError('HUMAN_APPROVAL_REQUIRED')
