from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple

HUMAN_ONLY_DOMAINS = {
    'PRODUCTION_RELEASE','PROTECTED_MAIN_MERGE','PRODUCTION_DATA_MUTATION',
    'AUTHORITY_WIDENING','CUSTOMER_COMMITMENT','BID_SUBMISSION',
    'PRICING_COMMITMENT','CONTRACT_COMMITMENT','FINANCIAL_COMMITMENT'
}

@dataclass(frozen=True)
class DecisionRecord:
    decision_id: str
    action: str
    evidence_state: str
    outcome: str
    human_verdict: str
    rationale: str

@dataclass(frozen=True)
class CorrectionRecord:
    correction_id: str
    decision_id: str
    prior_decision: str
    corrected_decision: str
    rationale: str

@dataclass(frozen=True)
class GoldenScenario:
    scenario_id: str
    input_class: str
    expected_disposition: str
    required_invariants: Tuple[str, ...]
    version: int = 1

@dataclass(frozen=True)
class OutcomeScore:
    correctness: float
    safety: float
    evidence_quality: float
    efficiency: float
    business_outcome: float

    def validate(self):
        for value in asdict(self).values():
            if value < 0 or value > 1:
                raise ValueError('SCORE_OUT_OF_RANGE')

    @property
    def weighted(self) -> float:
        self.validate()
        return round(
            0.30*self.correctness + 0.30*self.safety + 0.20*self.evidence_quality +
            0.10*self.efficiency + 0.10*self.business_outcome, 4
        )

class DecisionCorpus:
    def __init__(self): self._records: Dict[str, DecisionRecord] = {}
    def append(self, record: DecisionRecord):
        if record.decision_id in self._records: raise ValueError('DUPLICATE_DECISION_ID')
        self._records[record.decision_id] = record
    def all(self) -> List[DecisionRecord]: return list(self._records.values())

class HumanCorrectionLog:
    def __init__(self): self._records: Dict[str, CorrectionRecord] = {}
    def append(self, record: CorrectionRecord):
        if record.correction_id in self._records: raise ValueError('DUPLICATE_CORRECTION_ID')
        if not record.rationale.strip(): raise ValueError('RATIONALE_REQUIRED')
        self._records[record.correction_id] = record
    def all(self) -> List[CorrectionRecord]: return list(self._records.values())

class GoldenScenarioRegistry:
    def __init__(self): self._records: Dict[str, GoldenScenario] = {}
    def register(self, scenario: GoldenScenario):
        current = self._records.get(scenario.scenario_id)
        if current and scenario.version <= current.version: raise ValueError('NON_MONOTONIC_VERSION')
        self._records[scenario.scenario_id] = scenario
    def get(self, scenario_id: str) -> GoldenScenario: return self._records[scenario_id]

@dataclass(frozen=True)
class LearningProposal:
    proposal_id: str
    target: str
    proposed_change: str
    supporting_decisions: Tuple[str, ...]
    confidence: float
    disposition: str = 'PROPOSE_ONLY'

class LearningEngine:
    def propose(self, proposal_id: str, target: str, proposed_change: str,
                supporting_decisions: Tuple[str, ...], confidence: float,
                evidence_state: str) -> LearningProposal:
        if target in HUMAN_ONLY_DOMAINS: raise PermissionError('AUTHORITY_CHANGE_REQUIRES_HUMAN')
        if evidence_state in {'MISSING','CONTRADICTORY','STALE','UNKNOWN'}:
            raise ValueError('EVIDENCE_NOT_READY')
        if not supporting_decisions: raise ValueError('SUPPORTING_EVIDENCE_REQUIRED')
        if confidence < 0 or confidence > 1: raise ValueError('CONFIDENCE_OUT_OF_RANGE')
        return LearningProposal(proposal_id, target, proposed_change, supporting_decisions, confidence)

    def apply(self, proposal: LearningProposal):
        raise PermissionError('SELF_APPLY_FORBIDDEN')
