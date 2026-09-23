#!/usr/bin/env python3
from typing import Dict, Iterable
from financebridge_binding import FinanceBridgeBinding, ProviderConfig
from provider_route_evidence import RouteEvidence, verify_registry

REQUIRED_OPERATIONS=(
    "upsert_customer",
    "create_invoice",
    "record_payment",
    "submit_einvoice",
    "get_einvoice_status",
    "create_receipt_reference",
    "reconcile",
)

def preflight(config:ProviderConfig, route_evidence:Iterable[RouteEvidence])->Dict:
    binding=FinanceBridgeBinding(config)
    readiness=binding.readiness()
    if readiness["status"]!="PASS":
        return {
            "status":"HOLD",
            "reason":readiness["reason"],
            "stage":"CONFIG",
            "production_authority":False,
        }

    routes=verify_registry(REQUIRED_OPERATIONS,route_evidence)
    if routes["status"]!="PASS":
        return {
            "status":"HOLD",
            "reason":routes["reason"],
            "stage":"ROUTE_EVIDENCE",
            "detail":routes,
            "production_authority":False,
        }

    return {
        "status":"PASS",
        "reason":"SANDBOX_GOLDEN_PREFLIGHT_READY",
        "stage":"PREFLIGHT",
        "network_call_performed":False,
        "required_operations":list(REQUIRED_OPERATIONS),
        "production_authority":False,
    }

if __name__=="__main__":
    print({
        "status":"HOLD",
        "reason":"PRIVATE_PROVIDER_PROFILE_AND_ROUTE_EVIDENCE_REQUIRED",
        "production_authority":False
    })
