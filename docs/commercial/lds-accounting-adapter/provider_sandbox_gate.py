#!/usr/bin/env python3
import json
from pathlib import Path
from financebridge_binding import FinanceBridgeBinding, ProviderConfig

ROOT=Path(__file__).resolve().parent

def evaluate(config:ProviderConfig):
    matrix=json.loads((ROOT/"provider_capabilities.json").read_text())
    binding=FinanceBridgeBinding(config)
    config_status=binding.readiness()
    unverified=sorted(k for k,v in matrix["route_verification"].items() if not v)
    if config_status["status"]!="PASS":
        return {
            "status":"HOLD",
            "reason":config_status["reason"],
            "config_ready":False,
            "unverified_routes":unverified,
            "production_authority":False,
        }
    if unverified:
        return {
            "status":"HOLD",
            "reason":"PROVIDER_ROUTE_CAPABILITY_VERIFICATION_REQUIRED",
            "config_ready":True,
            "unverified_routes":unverified,
            "production_authority":False,
        }
    return {
        "status":"PASS",
        "reason":"FINANCEBRIDGE_STAGING_BINDING_READY",
        "config_ready":True,
        "unverified_routes":[],
        "production_authority":False,
    }

if __name__=="__main__":
    print(evaluate(ProviderConfig.from_env()))
