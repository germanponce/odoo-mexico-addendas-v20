# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
from .common import CfdiComplianceCommon


class TestCoordinados(CfdiComplianceCommon):

    def test_coordinado_relation_create(self):
        rel = self.env["l10n_mx.cfdi.coordinado.relation"].create({
            "name": "Convenio Demo 2026",
            "controladora_company_id": self.company.id,
            "coordinada_vat": "BBB020202BB2",
            "relation_type": "coordinados",
            "valid_from": "2026-01-01",
            "valid_to": "2026-12-31",
            "accept_cfdi_to_coordinada": True,
        })
        self.assertTrue(rel.active)
        self.assertEqual(rel.relation_type, "coordinados")
