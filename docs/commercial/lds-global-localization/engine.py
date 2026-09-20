#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

SUPPORTED={
"MY":{"locales":{"en-MY","ms-MY"},"currency":"MYR","timezone":"Asia/Kuala_Lumpur"},
"SG":{"locales":{"en-SG"},"currency":"SGD","timezone":"Asia/Singapore"},
"AU":{"locales":{"en-AU"},"currency":"AUD","timezone":"Australia/Sydney"},
"GB":{"locales":{"en-GB"},"currency":"GBP","timezone":"Europe/London"}
}

@dataclass(frozen=True)
class LocaleRequest:
    market:str
    locale:str
    pack_version:str
    policy_version:str
    translation_reviewed:bool

def resolve(r:LocaleRequest)->Dict:
    market=SUPPORTED.get(r.market)
    if not market:
        return {"status":"FALLBACK_REVIEW","risk_flags":["UNSUPPORTED_MARKET"],"production_activation_authorized":False}
    if r.locale not in market["locales"]:
        return {"status":"FALLBACK_REVIEW","risk_flags":["UNSUPPORTED_LOCALE"],"production_activation_authorized":False}
    flags=[]
    if not r.pack_version: flags.append("LOCALE_PACK_VERSION_REQUIRED")
    if not r.policy_version: flags.append("POLICY_VERSION_REQUIRED")
    if not r.translation_reviewed: flags.append("TRANSLATION_REVIEW_REQUIRED")
    return {
      "status":"READY_FOR_HUMAN_MARKET_REVIEW" if not flags else "REVIEW",
      "resolved_locale":r.locale,
      "resolved_currency_display":market["currency"],
      "resolved_timezone":market["timezone"],
      "risk_flags":flags,
      "production_activation_authorized":False
    }

def automatic_legal_translation_allowed()->bool:
    return False
