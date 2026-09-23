#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict, Optional
from urllib.parse import urljoin
import os

STAGING_BASE_URL = "https://api.staging.bukku.dev"
PRODUCTION_BASE_URL = "https://api.bukku.my"
DOCUMENTED_RATE_LIMIT_PER_MINUTE = 600

@dataclass(frozen=True)
class BukkuRoute:
    name: str
    method: str
    path: str
    verified: bool = False
    source: str = ""

@dataclass(frozen=True)
class BukkuConfig:
    environment: str
    access_token: str
    company_subdomain: str
    base_url: str

    @classmethod
    def from_env(cls) -> "BukkuConfig":
        environment=os.getenv("LD_BUKKU_ENV","staging").strip().lower()
        default_base=STAGING_BASE_URL if environment=="staging" else PRODUCTION_BASE_URL
        return cls(
            environment=environment,
            access_token=os.getenv("LD_BUKKU_ACCESS_TOKEN","").strip(),
            company_subdomain=os.getenv("LD_BUKKU_COMPANY_SUBDOMAIN","").strip(),
            base_url=os.getenv("LD_BUKKU_BASE_URL",default_base).strip().rstrip("/"),
        )

class BukkuBinding:
    """Fail-closed request builder. It performs no network calls."""

    def __init__(self, config:BukkuConfig):
        self.config=config

    def readiness(self) -> Dict:
        if self.config.environment!="staging":
            return {"status":"HOLD","reason":"PRODUCTION_ENVIRONMENT_FORBIDDEN_IN_P0"}
        if self.config.base_url!=STAGING_BASE_URL:
            return {"status":"HOLD","reason":"STAGING_BASE_URL_MISMATCH"}
        if not self.config.access_token:
            return {"status":"HOLD","reason":"BUKKU_ACCESS_TOKEN_REQUIRED"}
        if not self.config.company_subdomain:
            return {"status":"HOLD","reason":"BUKKU_COMPANY_SUBDOMAIN_REQUIRED"}
        return {
            "status":"PASS",
            "reason":"BUKKU_STAGING_CONFIG_READY",
            "environment":"staging",
            "base_url":self.config.base_url,
            "rate_limit_per_minute":DOCUMENTED_RATE_LIMIT_PER_MINUTE,
        }

    def headers(self) -> Dict[str,str]:
        ready=self.readiness()
        if ready["status"]!="PASS":
            raise ValueError(ready["reason"])
        return {
            "Authorization":f"Bearer {self.config.access_token}",
            "Company-Subdomain":self.config.company_subdomain,
            "Accept":"application/json",
            "Content-Type":"application/json",
        }

    def build_request(self, route:BukkuRoute, body:Optional[Dict]=None) -> Dict:
        ready=self.readiness()
        if ready["status"]!="PASS":
            return ready
        if not route.verified:
            return {
                "status":"HOLD",
                "reason":"BUKKU_ROUTE_NOT_VERIFIED",
                "route":route.name,
            }
        if not route.path.startswith("/"):
            return {"status":"HOLD","reason":"BUKKU_ROUTE_PATH_INVALID","route":route.name}
        method=route.method.upper()
        if method not in {"GET","POST","PUT","PATCH","DELETE"}:
            return {"status":"HOLD","reason":"BUKKU_ROUTE_METHOD_INVALID","route":route.name}
        return {
            "status":"PASS",
            "environment":"staging",
            "method":method,
            "url":urljoin(self.config.base_url+"/",route.path.lstrip("/")),
            "headers":self.headers(),
            "body":body,
            "network_call_performed":False,
            "production_authority":False,
        }

    def redacted_config(self) -> Dict:
        token=self.config.access_token
        redacted="***" if token else ""
        return {
            "environment":self.config.environment,
            "access_token":redacted,
            "company_subdomain":self.config.company_subdomain,
            "base_url":self.config.base_url,
        }
