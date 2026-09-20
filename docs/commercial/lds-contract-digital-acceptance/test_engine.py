#!/usr/bin/env python3
import unittest
from engine import *

class Tests(unittest.TestCase):
    def test_explicit_accept_required(self):
        x=AcceptanceInput("c1",("h1",),"s1","t1","PAGE_VIEW","2026-09-20T10:00:00Z","e1")
        self.assertEqual(create_record(x)["status"],"REVIEW")
    def test_record_binds_hashes(self):
        x=AcceptanceInput("c1",("h1","h2"),"s1","t1","EXPLICIT_ACCEPT","2026-09-20T10:00:00Z","e1")
        r=create_record(x)
        self.assertEqual(r["status"],"ACCEPTANCE_RECORDED")
        self.assertEqual(r["bound_document_hashes"],["h1","h2"])
        self.assertTrue(r["immutable"])
    def test_no_silent_consent(self):
        self.assertFalse(infer_consent_from_silence())

if __name__=="__main__": unittest.main()
