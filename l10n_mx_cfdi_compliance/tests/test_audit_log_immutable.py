# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
from odoo.exceptions import UserError
from .common import CfdiComplianceCommon


class TestAuditLogImmutable(CfdiComplianceCommon):

    def test_cannot_unlink_audit_log(self):
        log = self.AuditLog.log("TEST_ACTION", payload={"x": 1})
        with self.assertRaises(UserError):
            log.unlink()

    def test_cannot_write_audit_log(self):
        log = self.AuditLog.log("TEST_ACTION_2", payload={"x": 2})
        with self.assertRaises(UserError):
            log.write({"action": "TAMPERED"})

    def test_chain_integrity(self):
        self.AuditLog.log("ACTION_A", payload={"k": 1})
        self.AuditLog.log("ACTION_B", payload={"k": 2})
        self.AuditLog.log("ACTION_C", payload={"k": 3})
        self.assertTrue(self.AuditLog.action_verify_chain())
