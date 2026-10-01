# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
from .common import CfdiComplianceCommon, load_fixture
from ..engine.parser.cfdi_parser import parse_cfdi, is_cfdi_xml


class TestParser(CfdiComplianceCommon):

    def test_is_cfdi_xml_detects_valid(self):
        raw = load_fixture("cfdi_valid.xml")
        self.assertTrue(is_cfdi_xml(raw))

    def test_parse_extracts_core_fields(self):
        raw = load_fixture("cfdi_valid.xml")
        dto = parse_cfdi(raw)
        self.assertEqual(dto.uuid, "11111111-2222-3333-4444-555555555555")
        self.assertEqual(dto.rfc_emisor, "AAA010101AAA")
        self.assertEqual(dto.rfc_receptor, "XAXX010101000")
        self.assertEqual(dto.metodo_pago, "PUE")
        self.assertEqual(dto.forma_pago, "03")
        self.assertEqual(float(dto.total), 1160.00)

    def test_parse_rejects_non_xml(self):
        self.assertFalse(is_cfdi_xml(b"not xml at all"))
