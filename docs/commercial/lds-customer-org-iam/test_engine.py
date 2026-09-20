#!/usr/bin/env python3
import unittest
from engine import *

class Tests(unittest.TestCase):
    def test_cross_org_denied(self):
        self.assertEqual(authorize(AccessRequest("o1","o2","OWNER","read"))["decision"],"DENY")
    def test_finance_cannot_manage_technical(self):
        self.assertEqual(authorize(AccessRequest("o1","o1","FINANCE","manage_technical"))["decision"],"DENY")
    def test_viewer_read_only(self):
        self.assertEqual(authorize(AccessRequest("o1","o1","VIEWER","read"))["decision"],"ALLOW")
        self.assertEqual(authorize(AccessRequest("o1","o1","VIEWER","manage_project"))["decision"],"DENY")
    def test_default_deny(self):
        self.assertFalse(default_allow())

if __name__=="__main__": unittest.main()
