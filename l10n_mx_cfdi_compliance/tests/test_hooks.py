# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
from odoo.exceptions import UserError
from .common import CfdiComplianceCommon, load_fixture


class TestHooks(CfdiComplianceCommon):

    def test_account_move_blocked_when_cfdi_blocked(self):
        raw = load_fixture("cfdi_valid.xml")
        att = self._attach_xml(raw)
        cfdi = self.CfdiDoc.search([("attachment_id", "=", att.id)], limit=1)
        # Force a blocked state to test hook
        cfdi.with_context(_audit_internal_write=True).write({"compliance_state": "blocked"})

        partner = self.env["res.partner"].create({"name": "Vendor Test"})
        move = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": partner.id,
            "cfdi_document_id": cfdi.id,
            "invoice_line_ids": [(0, 0, {
                "name": "x",
                "quantity": 1,
                "price_unit": 100,
            })],
        })
        with self.assertRaises(UserError):
            move.action_post()
