#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict, Optional
from urllib.parse import urlparse, urljoin
import os

@dataclass(frozen=True)
class ProviderRoute:
    name: str
    method: str
    path: str
    verified: bool = False
    source: str = ""

@dataclass(frozen=True)
class ProviderConfig:
    environment: str
    access_token: str
    tenant_header_name: str
    tenant_key: str
    base_url: str
    rate_limit_per_minute: int

    @classmethod
    def from_env(cls) -> "ProviderConfig":
        raw_limit=os.getenv("LD_FINANCEBRIDGE_RATE_LIMIT_PER_MINUTE","0").strip()
        try:
            rate_limit=int(raw_limit or "0")
        except ValueError:
            rate_limit=0
        return cls(
            environment=os.getenv("LD_FINANCEBRIDGE_ENV","staging").strip().lower(),
            access_token=os.getenv("LD_FINANCEBRIDGE_ACCESS_TOKEN","").strip(),
            tenant_header_name=os.getenv("LD_FINANCEBRIDGE_TENANT_HEADER","").strip(),
            tenant_key=os.getenv("LD_FINANCEBRIDGE_TENANT_KEY","").strip(),
            base_url=os.getenv("LD_FINANCEBRIDGE_BASE_URL","").strip().rstrip("/"),
            rate_limit_per_minute=rate_limit,
        )

class FinanceBridgeBinding:
    """Vendor-neutral fail-closed request builder. It performs no network calls."""

    def __init__(self, config:ProviderConfig):
        self.config=config

    def readiness(self) -> Dict:
        if self.config.environment!="staging":
            return {"status":"HOLD","reason":"PRODUCTION_ENVIRONMENT_FORBIDDEN_IN_P0"}
        parsed=urlparse(self.config.base_url)
        if parsed.scheme!="https" or not parsed.netloc:
            return {"status":"HOLD","reason":"STAGING_BASE_URL_REQUIRED"}
        if not self.config.access_token:
            return {"status":"HOLD","reason":"PROVIDER_ACCESS_TOKEN_REQUIRED"}
        if bool(self.config.tenant_header_name) != bool(self.config.tenant_key):
            return {"status":"HOLD","reason":"TENANT_HEADER_CONFIGURATION_INCOMPLETE"}
        if self.config.rate_limit_per_minute <= 0:
            return {"status":"HOLD","reason":"PROVIDER_RATE_LIMIT_REQUIRED"}
        return {
            "status":"PASS",
            "reason":"FINANCEBRIDGE_STAGING_CONFIG_READY",
            "environment":"staging",
            "base_url":self.config.base_url,
            "rate_limit_per_minute":self.config.rate_limit_per_minute,
        }

    def headers(self) -> Dict[str,str]:
        ready=self.readiness()
        if ready["status"]!="PASS":
            raise ValueError(ready["reason"])
        headers={
            "Authorization":f"Bearer {self.config.access_token}",
            "Accept":"application/json",
            "Content-Type":"application/json",
        }
        if self.config.tenant_header_name:
            headers[self.config.tenant_header_name]=self.config.tenant_key
        return headers

    def build_request(self, route:ProviderRoute, body:Optional[Dict]=None) -> Dict:
        ready=self.readiness()
        if ready["status"]!="PASS":
            return ready
        if not route.verified:
            return {"status":"HOLD","reason":"PROVIDER_ROUTE_NOT_VERIFIED","route":route.name}
        if not route.path.startswith("/"):
            return {"status":"HOLD","reason":"PROVIDER_ROUTE_PATH_INVALID","route":route.name}
        method=route.method.upper()
        if method not in {"GET","POST","PUT","PATCH","DELETE"}:
            return {"status":"HOLD","reason":"PROVIDER_ROUTE_METHOD_INVALID","route":route.name}
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
        return {
            "environment":self.config.environment,
            "access_token":"***" if self.config.access_token else "",
            "tenant_header_name":self.config.tenant_header_name,
            "tenant_key":"***" if self.config.tenant_key else "",
            "base_url":self.config.base_url,
            "rate_limit_per_minute":self.config.rate_limit_per_minute,
        }
