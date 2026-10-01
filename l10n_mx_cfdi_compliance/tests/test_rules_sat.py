# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
from .common import CfdiComplianceCommon, load_fixture


class TestRulesSat(CfdiComplianceCommon):

    def test_rule_sat_001_xml_valido_passes_for_valid(self):
        raw = load_fixture("cfdi_valid.xml")
        att = self._attach_xml(raw)
        cfdi = self.CfdiDoc.search([("attachment_id", "=", att.id)], limit=1)
        codes = cfdi.result_ids.mapped("rule_code")
        self.assertIn("SAT_001_XML_VALIDO", codes)
        sat001 = cfdi.result_ids.filtered(lambda r: r.rule_code == "SAT_001_XML_VALIDO")
        self.assertTrue(sat001.passed)

    def test_rule_sat_050_rfc_valido(self):
        raw = load_fixture("cfdi_valid.xml")
        att = self._attach_xml(raw)
        cfdi = self.CfdiDoc.search([("attachment_id", "=", att.id)], limit=1)
        rfc_rule = cfdi.result_ids.filtered(lambda r: r.rule_code == "SAT_050_RFC_VALIDO")
        self.assertTrue(rfc_rule)
        self.assertTrue(rfc_rule.passed)
