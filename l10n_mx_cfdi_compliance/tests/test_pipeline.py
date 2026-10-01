# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
from .common import CfdiComplianceCommon, load_fixture


class TestPipeline(CfdiComplianceCommon):

    def test_attachment_creates_cfdi_document_and_runs_pipeline(self):
        raw = load_fixture("cfdi_valid.xml")
        att = self._attach_xml(raw)
        cfdi = self.CfdiDoc.search([("attachment_id", "=", att.id)], limit=1)
        self.assertTrue(cfdi, "ir.attachment hook should have created a cfdi document")
        self.assertEqual(cfdi.uuid, "11111111-2222-3333-4444-555555555555")
        self.assertIn(cfdi.compliance_state, (
            "passed", "warning", "authorization_required", "blocked", "error",
        ))
        self.assertTrue(cfdi.result_ids, "Pipeline should record at least one rule result")

    def test_invalid_xml_does_not_create_cfdi(self):
        att = self._attach_xml(b"<root/>", filename="foo.xml")
        cfdi = self.CfdiDoc.search([("attachment_id", "=", att.id)])
        self.assertFalse(cfdi)
