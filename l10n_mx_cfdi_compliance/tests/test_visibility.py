# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
"""Pruebas de visibilidad por TIPO + DIRECCION via campos en res.users
(can_see_compliance_*) y la ir.rule global. Reemplaza el esquema de grupos."""
import base64

from .common import CfdiComplianceCommon


class TestComplianceVisibility(CfdiComplianceCommon):

    def _mkdoc(self, uuid, tipo, emisor, receptor):
        att = self.env["ir.attachment"].create({
            "name": uuid + ".xml", "datas": base64.b64encode(b"<cfdi/>")})
        return self.CfdiDoc.create({
            "uuid": uuid, "tipo_comprobante": tipo, "rfc_emisor": emisor,
            "rfc_receptor": receptor, "attachment_id": att.id,
            "company_id": self.company.id, "total": 1000.0})

    def _mkuser(self, login, groups, **vals):
        gfield = "group_ids" if "group_ids" in self.env["res.users"]._fields else "groups_id"
        u = self.env["res.users"].create({"name": login, "login": login})
        gids = [self.env.ref(g).id for g in groups] + [self.env.ref("base.group_user").id]
        u.write({gfield: [(6, 0, gids)]})
        if vals:
            u.write(vals)
        return u

    def setUp(self):
        super().setUp()
        if not self.company.vat:
            self.company.vat = "AAA010101AA1"
        crfc = (self.company.vat or "").strip().upper()
        self._mkdoc("VIS-RI", "I", "PROV010101AA1", crfc)   # recibido ingreso
        self._mkdoc("VIS-EI", "I", crfc, "CLI010101BB2")    # emitido ingreso
        self._mkdoc("VIS-RN", "N", "PROV010101AA1", crfc)   # recibido nomina
        self._mkdoc("VIS-EN", "N", crfc, "EMP010101CC3")    # emitido nomina

    def _seen(self, user):
        return set(self.CfdiDoc.with_user(user).search(
            [("uuid", "like", "VIS-")]).mapped("uuid"))

    # ---- helpers ----
    def test_get_allowed(self):
        u = self._mkuser(
            "vis_h", ["l10n_mx_cfdi_compliance.group_cfdi_compliance_user"],
            can_see_compliance_egreso=False, can_see_compliance_nomina=False,
            can_see_compliance_emitido=False)
        self.assertEqual(set(u.get_allowed_compliance_types()), {"I", "P", "T"})
        self.assertEqual(set(u.get_allowed_compliance_directions()), {"recibido"})

    def test_has_access(self):
        u = self._mkuser("vis_a", ["l10n_mx_cfdi_compliance.group_cfdi_compliance_user"])
        self.assertTrue(u.has_cfdi_compliance_access)
        n = self._mkuser("vis_na", [])
        self.assertFalse(n.has_cfdi_compliance_access)

    # ---- visibilidad ----
    def test_ingreso_recibido_only(self):
        u = self._mkuser(
            "vis_ri", ["l10n_mx_cfdi_compliance.group_cfdi_compliance_user"],
            can_see_compliance_ingreso=True, can_see_compliance_egreso=False,
            can_see_compliance_pago=False, can_see_compliance_nomina=False,
            can_see_compliance_traslado=False,
            can_see_compliance_emitido=False, can_see_compliance_recibido=True)
        self.assertEqual(self._seen(u), {"VIS-RI"})

    def test_nomina_hidden_by_default(self):
        u = self._mkuser("vis_def", ["l10n_mx_cfdi_compliance.group_cfdi_compliance_user"])
        seen = self._seen(u)
        self.assertNotIn("VIS-RN", seen)
        self.assertNotIn("VIS-EN", seen)
        self.assertIn("VIS-RI", seen)
        self.assertIn("VIS-EI", seen)

    def test_nomina_visible_when_enabled(self):
        u = self._mkuser(
            "vis_nom", ["l10n_mx_cfdi_compliance.group_cfdi_compliance_user"],
            can_see_compliance_nomina=True)
        self.assertEqual(self._seen(u), {"VIS-RI", "VIS-EI", "VIS-RN", "VIS-EN"})

    def test_manager_bypass(self):
        m = self._mkuser(
            "vis_mgr", ["l10n_mx_cfdi_compliance.group_cfdi_compliance_manager"],
            can_see_compliance_nomina=False, can_see_compliance_emitido=False)
        # Manager ve TODO pese a tener campos restringidos (bypass).
        self.assertEqual(self._seen(m), {"VIS-RI", "VIS-EI", "VIS-RN", "VIS-EN"})
