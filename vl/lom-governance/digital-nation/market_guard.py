"""LOM Market P0 contract guard."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List

ALLOWED_MARKETS={"SERVICE","WORK_GIG","DIGITAL_GOOD_IP","B2B","VIRTUAL_ASSET"}
ALLOWED_P0_PRICE={"FIXED_PRICE","REQUEST_QUOTE","PACKAGE_PRICE"}

def load_contract(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def validate_market_contract(c: Dict[str, Any]) -> List[str]:
    errors=[]
    if c.get("schema")!="lom.digital-nation.market/1":
        errors.append("SCHEMA_MISMATCH")
    if c.get("status")!="DRAFT_NON_PRODUCTION":
        errors.append("STATUS_MUST_BE_DRAFT_NON_PRODUCTION")
    if c.get("production_activation_authorized") is not False:
        errors.append("PRODUCTION_AUTHORITY_MUST_BE_FALSE")
    if c.get("owner")!="LD Commerce":
        errors.append("COMMERCE_OWNER_MISMATCH")
    if c.get("trust_owner")!="LOM Trust":
        errors.append("TRUST_OWNER_MISMATCH")
    markets=set(c.get("market_types",[]))
    if not markets or not markets.issubset(ALLOWED_MARKETS):
        errors.append("INVALID_MARKET_TYPES")
    modes=set(c.get("p0_price_modes",[]))
    if not modes or not modes.issubset(ALLOWED_P0_PRICE):
        errors.append("INVALID_P0_PRICE_MODE")
    if len(set(c.get("p0_entry_points",[])))!=4:
        errors.append("P0_ENTRY_POINTS_REQUIRED")
    return errors

def validate_listing(listing: Dict[str, Any], contract: Dict[str, Any]) -> Dict[str, Any]:
    missing=[f for f in contract.get("required_listing_fields",[]) if not listing.get(f)]
    if missing:
        return {"decision":"HOLD","reason":"MISSING_REQUIRED_FIELDS","missing":missing}
    if listing.get("market_type") not in contract.get("market_types",[]):
        return {"decision":"HOLD","reason":"UNSUPPORTED_MARKET_TYPE"}
    if listing.get("price_mode") not in contract.get("p0_price_modes",[]):
        return {"decision":"HOLD","reason":"UNSUPPORTED_PRICE_MODE"}
    if listing.get("seller_authority_verified") is not True:
        return {"decision":"HOLD","reason":"SELLER_AUTHORITY_UNVERIFIED"}
    if listing.get("policy_allowed") is not True:
        return {"decision":"HOLD","reason":"POLICY_NOT_ALLOWED"}
    return {
        "decision":"ALLOW_PREVIEW_LISTING",
        "listing_id":listing["listing_id"],
        "production_authority":False,
        "live_payment_authority":False
    }
