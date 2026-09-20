#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class RecoveryEvidence:
    rpo_minutes:int
    rto_minutes:int
    backup_age_minutes:int
    restore_test_age_days:int
    primary_provider_up:bool
    fallback_available:bool
    data_integrity_uncertain:bool=False

def assess(e:RecoveryEvidence)->Dict:
    flags=[]
    if e.rpo_minutes < 0 or e.rto_minutes < 0:
        return {"status":"REVIEW","risk_flags":["INVALID_RECOVERY_POLICY"],"restore_authorized":False}
    if e.backup_age_minutes > e.rpo_minutes:
        flags.append("RPO_BREACH_OR_BACKUP_STALE")
    if e.restore_test_age_days > 90:
        flags.append("RESTORE_TEST_STALE")
    if e.data_integrity_uncertain:
        flags.append("DATA_INTEGRITY_UNCERTAIN")
    if not e.primary_provider_up and not e.fallback_available:
        flags.append("NO_FALLBACK_AVAILABLE")
    status="RECOVERY_EVIDENCE_READY" if not flags else "REVIEW"
    fallback="CONSIDER_CONTROLLED_FALLBACK" if (not e.primary_provider_up and e.fallback_available and not e.data_integrity_uncertain) else "NO_AUTOMATIC_FAILOVER"
    return {
      "status":status,
      "risk_flags":flags,
      "fallback_recommendation":fallback,
      "restore_authorized":False,
      "production_failover_authorized":False,
      "human_approval_required":True
    }

def automatic_restore_allowed()->bool:
    return False
