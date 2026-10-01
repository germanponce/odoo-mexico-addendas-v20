# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
from odoo.tests import tagged
from .common import CfdiComplianceCommon, load_fixture


@tagged("multi_company")
class TestMultiCompany(CfdiComplianceCommon):

    def test_isolation_per_company(self):
        company_b = self.env["res.company"].create({"name": "Otra SA"})
        self.env["res.company"]._l10n_mx_cfdi_create_default_profile()
        raw = load_fixture("cfdi_valid.xml")
        att_a = self._attach_xml(raw, "a.xml")
        cfdi_a = self.CfdiDoc.search([("attachment_id", "=", att_a.id)], limit=1)
        self.assertEqual(cfdi_a.company_id, self.company)

        cfdi_other = self.CfdiDoc.with_company(company_b).search([
            ("id", "=", cfdi_a.id),
        ])
        # Acceso bloqueado por ir.rule (no aparece en otra compania)
        self.assertFalse(cfdi_other)
