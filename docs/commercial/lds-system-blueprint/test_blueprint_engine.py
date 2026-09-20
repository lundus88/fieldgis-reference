#!/usr/bin/env python3
import unittest
from blueprint_engine import *

class BlueprintTests(unittest.TestCase):
  def test_missing_scope(self):
    b=Blueprint("","flow",("m",),("a",))
    self.assertEqual(assess(b)["status"],"NEED_MORE_INFO")
  def test_unresolved_assumptions_block_quote_ready(self):
    b=Blueprint("p","flow",("m",),("a",),unresolved_assumptions=("API access",))
    self.assertFalse(assess(b)["quote_ready"])
  def test_customer_approval_makes_quote_ready_not_build_authorized(self):
    b=Blueprint("p","flow",("m",),("a",),customer_approved=True)
    r=assess(b)
    self.assertTrue(r["quote_ready"])
    self.assertFalse(r["build_authorized"])
  def test_freeze_requires_approval(self):
    b=Blueprint("p","flow",("m",),("a",))
    self.assertEqual(freeze_snapshot(b,1)["decision"],"HOLD")
  def test_frozen_snapshot_requires_change_request(self):
    b=Blueprint("p","flow",("m",),("a",),customer_approved=True)
    self.assertEqual(freeze_snapshot(b,2)["changes_require"],"CHANGE_REQUEST")

if __name__=="__main__": unittest.main()
