from dataclasses import dataclass
from typing import Iterable, List

HUMAN_ONLY = {
    'PROTECTED_MAIN_MERGE','PRODUCTION_RELEASE','PRODUCTION_DATA_MUTATION',
    'AUTHORITY_WIDENING','AUTH_SECURITY_POLICY_CHANGE','CUSTOMER_COMMITMENT',
    'BID_SUBMISSION','PRICING_COMMITMENT','CONTRACT_COMMITMENT',
    'FINANCIAL_COMMITMENT','DATA_DELETION'
}

@dataclass(frozen=True)
class PortfolioSignal:
    project_id: str
    health: str
    evidence_state: str
    evidence_ref: str
    target: str
    risk: str
    reversible: bool
    production: bool
    physical_verification_required: bool = False
    physical_verification_complete: bool = True

@dataclass(frozen=True)
class OpsDecision:
    project_id: str
    action_class: str
    priority: int
    next_best_action: str
    reason: str

class DailyOpsCockpit:
    def classify(self, signal: PortfolioSignal) -> OpsDecision:
        if signal.evidence_state != 'READY' or not signal.evidence_ref.strip():
            return OpsDecision(signal.project_id,'HOLD',100,'Refresh trustworthy evidence before action.','EVIDENCE_NOT_READY')
        if signal.physical_verification_required and not signal.physical_verification_complete:
            return OpsDecision(signal.project_id,'HOLD',95,'Complete required physical verification and attach evidence.','PHYSICAL_VERIFICATION_REQUIRED')
        if signal.target in HUMAN_ONLY or signal.production or signal.risk == 'HIGH':
            return OpsDecision(signal.project_id,'HUMAN_REVIEW',90,'Prepare a decision package for human approval; do not execute consequential action.','HUMAN_BOUNDARY')
        if not signal.reversible:
            return OpsDecision(signal.project_id,'HOLD',85,'Redesign as a reversible bounded change before staging.','REVERSIBILITY_REQUIRED')
        if signal.health in {'BLOCKED','HOLD'}:
            return OpsDecision(signal.project_id,'AUTO_PREPARE',80,'Prepare a reversible non-production remediation and validation package.','BOUNDED_REMEDIATION')
        if signal.health == 'REVIEW':
            return OpsDecision(signal.project_id,'AUTO_PREPARE',60,'Prepare evidence review and bounded improvement PR candidate.','REVIEW_WORK')
        return OpsDecision(signal.project_id,'MONITOR',20,'Continue read-only monitoring and refresh evidence.','NO_CURRENT_BLOCKER')

    def build(self, signals: Iterable[PortfolioSignal]) -> List[OpsDecision]:
        decisions = [self.classify(s) for s in signals]
        decisions.sort(key=lambda d: (-d.priority, d.project_id))
        return decisions

    def autonomous_ceiling(self) -> str:
        return 'PREPARE_PR'

    def merge_protected_main(self):
        raise PermissionError('HUMAN_APPROVAL_REQUIRED')

    def deploy_production(self):
        raise PermissionError('HUMAN_APPROVAL_REQUIRED')
