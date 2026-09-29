import unittest
from pathlib import Path

from market_guard import load_contract, validate_listing, validate_market_contract

ROOT=Path(__file__).resolve().parent
CONTRACT=ROOT/"market-contract-v1.json"

class MarketGuardTests(unittest.TestCase):
    def setUp(self):
        self.contract=load_contract(CONTRACT)
        self.listing={
            "listing_id":"listing_preview_001",
            "seller_id":"business_preview_001",
            "market_type":"SERVICE",
            "title":"Website service",
            "description":"Preview service listing",
            "category":"DIGITAL_SERVICE",
            "price_mode":"REQUEST_QUOTE",
            "scope":"Defined in approved offer",
            "fulfilment_method":"DIGITAL_DELIVERY",
            "delivery_terms":"Preview only",
            "policy_classification":"STANDARD",
            "seller_authority_verified":True,
            "policy_allowed":True
        }

    def test_contract_is_valid(self):
        self.assertEqual(validate_market_contract(self.contract),[])

    def test_preview_listing_can_be_admitted(self):
        out=validate_listing(self.listing,self.contract)
        self.assertEqual(out["decision"],"ALLOW_PREVIEW_LISTING")
        self.assertFalse(out["production_authority"])
        self.assertFalse(out["live_payment_authority"])

    def test_unverified_seller_holds(self):
        self.listing["seller_authority_verified"]=False
        out=validate_listing(self.listing,self.contract)
        self.assertEqual(out["decision"],"HOLD")
        self.assertEqual(out["reason"],"SELLER_AUTHORITY_UNVERIFIED")

    def test_unsupported_price_mode_holds(self):
        self.listing["price_mode"]="UNREVIEWED_AUCTION"
        out=validate_listing(self.listing,self.contract)
        self.assertEqual(out["decision"],"HOLD")
        self.assertEqual(out["reason"],"UNSUPPORTED_PRICE_MODE")

    def test_policy_blocked_listing_holds(self):
        self.listing["policy_allowed"]=False
        out=validate_listing(self.listing,self.contract)
        self.assertEqual(out["decision"],"HOLD")
        self.assertEqual(out["reason"],"POLICY_NOT_ALLOWED")

if __name__=="__main__":
    unittest.main()
