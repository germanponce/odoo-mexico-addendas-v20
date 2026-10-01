# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
"""Pruebas unitarias de reglas de Nomina (Etapa 1: A internas + F contable).

Cada regla se prueba en aislamiento (caso PASS y caso FAIL) construyendo un DTO
de nomina y un contexto minimo, sin depender del flujo attachment->pipeline.
Las reglas F (contable) se prueban con una poliza simulada (SimpleNamespace).
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from .common import CfdiComplianceCommon
from odoo.addons.l10n_mx_cfdi_compliance.engine.context import CfdiValidationContext
from odoo.addons.l10n_mx_cfdi_compliance.engine.parser.cfdi_parser import CfdiDocumentDTO
from odoo.addons.l10n_mx_cfdi_compliance.engine.parser.complementos.nomina12 import (
    NominaDTO, NominaPercepcion, NominaDeduccion, NominaOtroPago, NominaHorasExtra,
)
from odoo.addons.l10n_mx_cfdi_compliance.engine.rules.nomina import internas as A
from odoo.addons.l10n_mx_cfdi_compliance.engine.rules.nomina import contable as F


class TestRulesNomina(CfdiComplianceCommon):

    # ----------------- builders -----------------
    def _nomina(self, **kw):
        base = dict(
            version="1.2", tipo_nomina="O",
            fecha_pago=date(2026, 5, 15),
            fecha_inicial_pago=date(2026, 5, 1),
            fecha_final_pago=date(2026, 5, 15),
            num_dias_pagados=Decimal("15"),
            total_percepciones=Decimal("10000"),
            total_deducciones=Decimal("2500"),
            total_otros_pagos=Decimal("500"),
            curp="XEXX010101HNEXXXA4", nss="12345678901", num_empleado="EMP001",
            tipo_contrato="01", tipo_jornada="01", tipo_regimen="02", riesgo_puesto="1",
            percepciones=[NominaPercepcion(
                tipo_percepcion="001", clave="P001", concepto="Sueldo",
                importe_gravado=Decimal("9000"), importe_exento=Decimal("1000"))],
            deducciones=[NominaDeduccion(
                tipo_deduccion="001", clave="D001", concepto="IMSS",
                importe=Decimal("500"))],
            otros_pagos=[NominaOtroPago(
                tipo_otro_pago="002", clave="O002", concepto="Subsidio",
                importe=Decimal("500"))],
        )
        base.update(kw)
        return NominaDTO(**base)

    def _cfdi(self, nomina=None, **kw):
        d = dict(uuid="12345678-1234-1234-1234-123456789012",
                 rfc_emisor="EMP010101AAA", rfc_receptor="XAXX010101000",
                 total=Decimal("8000"), tipo_comprobante="N")
        d.update(kw)
        nom = nomina if nomina is not None else self._nomina()
        return CfdiDocumentDTO(nomina=nom, **d)

    def _ctx(self, cfdi, cfdi_record=None):
        return CfdiValidationContext(
            env=self.env, company=self.company,
            cfdi_record=cfdi_record if cfdi_record is not None else self.CfdiDoc,
            cfdi=cfdi, profile=self.profile)

    def _ok(self, rule, cfdi, cfdi_record=None):
        return rule.execute(self._ctx(cfdi, cfdi_record)).passed

    def _rec_con_move(self, **move_kw):
        m = dict(state="posted", company_id=self.company, date=date(2026, 5, 31),
                 amount_total=8000.0, name="AJ/2026/001")
        m.update(move_kw)
        return SimpleNamespace(related_move_id=SimpleNamespace(**m),
                               company_id=self.company)

    # ----------------- parser -----------------
    def test_parser_neto(self):
        self.assertEqual(self._nomina().neto, Decimal("8000"))

    # ----------------- A: identificacion -----------------
    def test_nom001_uuid_presente(self):
        self.assertTrue(self._ok(A.RuleNomUuidPresente(), self._cfdi()))
        self.assertFalse(self._ok(A.RuleNomUuidPresente(), self._cfdi(uuid="")))

    def test_nom002_uuid_valido(self):
        self.assertTrue(self._ok(A.RuleNomUuidValido(), self._cfdi()))
        self.assertFalse(self._ok(A.RuleNomUuidValido(), self._cfdi(uuid="NO-ES-UUID")))

    def test_nom003_rfc_emisor(self):
        self.assertTrue(self._ok(A.RuleNomRfcEmisor(), self._cfdi()))
        self.assertFalse(self._ok(A.RuleNomRfcEmisor(), self._cfdi(rfc_emisor="")))

    def test_nom004_rfc_receptor(self):
        self.assertTrue(self._ok(A.RuleNomRfcReceptor(), self._cfdi()))
        self.assertFalse(self._ok(A.RuleNomRfcReceptor(), self._cfdi(rfc_receptor="")))

    def test_nom005_curp(self):
        self.assertTrue(self._ok(A.RuleNomCurpPresente(), self._cfdi()))
        self.assertFalse(self._ok(A.RuleNomCurpPresente(),
                                  self._cfdi(nomina=self._nomina(curp=""))))

    def test_nom006_nss(self):
        self.assertTrue(self._ok(A.RuleNomNssPresente(), self._cfdi()))
        self.assertFalse(self._ok(A.RuleNomNssPresente(),
                                  self._cfdi(nomina=self._nomina(nss=""))))

    def test_nom007_num_empleado(self):
        self.assertTrue(self._ok(A.RuleNomNumEmpleado(), self._cfdi()))
        self.assertFalse(self._ok(A.RuleNomNumEmpleado(),
                                  self._cfdi(nomina=self._nomina(num_empleado=""))))

    # ----------------- A: periodo -----------------
    def test_nom008_fechas_periodo(self):
        self.assertTrue(self._ok(A.RuleNomFechasPeriodo(), self._cfdi()))
        bad = self._nomina(fecha_inicial_pago=date(2026, 5, 20),
                           fecha_final_pago=date(2026, 5, 1))
        self.assertFalse(self._ok(A.RuleNomFechasPeriodo(), self._cfdi(nomina=bad)))

    def test_nom009_fecha_pago(self):
        self.assertTrue(self._ok(A.RuleNomFechaPagoEnPeriodo(), self._cfdi()))
        bad = self._nomina(fecha_pago=date(2026, 4, 1))
        self.assertFalse(self._ok(A.RuleNomFechaPagoEnPeriodo(), self._cfdi(nomina=bad)))

    def test_nom010_num_dias(self):
        self.assertTrue(self._ok(A.RuleNomNumDiasPagados(), self._cfdi()))
        self.assertFalse(self._ok(A.RuleNomNumDiasPagados(),
                                  self._cfdi(nomina=self._nomina(num_dias_pagados=Decimal("0")))))

    # ----------------- A: importes -----------------
    def test_nom011_percepciones(self):
        self.assertTrue(self._ok(A.RuleNomTotalPercepciones(), self._cfdi()))
        self.assertFalse(self._ok(A.RuleNomTotalPercepciones(),
                                  self._cfdi(nomina=self._nomina(total_percepciones=Decimal("-1")))))

    def test_nom012_deducciones(self):
        self.assertTrue(self._ok(A.RuleNomTotalDeducciones(), self._cfdi()))
        self.assertFalse(self._ok(A.RuleNomTotalDeducciones(),
                                  self._cfdi(nomina=self._nomina(total_deducciones=Decimal("-1")))))

    def test_nom013_otros_pagos(self):
        self.assertTrue(self._ok(A.RuleNomTotalOtrosPagos(), self._cfdi()))
        self.assertFalse(self._ok(A.RuleNomTotalOtrosPagos(),
                                  self._cfdi(nomina=self._nomina(total_otros_pagos=Decimal("-1")))))

    def test_nom014_neto_cuadra(self):
        self.assertTrue(self._ok(A.RuleNomNetoCuadra(), self._cfdi()))
        self.assertFalse(self._ok(A.RuleNomNetoCuadra(), self._cfdi(total=Decimal("7777"))))

    # ----------------- A: catalogos -----------------
    def test_nom015_catalogos(self):
        self.assertTrue(self._ok(A.RuleNomCatalogos(), self._cfdi()))
        self.assertFalse(self._ok(A.RuleNomCatalogos(),
                                  self._cfdi(nomina=self._nomina(tipo_contrato="88"))))

    # ----------------- A: horas extra -----------------
    def test_nom016_horas_extra(self):
        self.assertTrue(self._ok(A.RuleNomHorasExtra(), self._cfdi()))
        he_bad = NominaPercepcion(
            tipo_percepcion="019", clave="P019", concepto="HE",
            importe_gravado=Decimal("0"), importe_exento=Decimal("100"),
            horas_extra=[NominaHorasExtra(dias=0, tipo_horas="99",
                                          horas_extra=0, importe_pagado=Decimal("100"))])
        self.assertFalse(self._ok(A.RuleNomHorasExtra(),
                                  self._cfdi(nomina=self._nomina(percepciones=[he_bad]))))

    # ----------------- applies (solo nomina) -----------------
    def test_applies_solo_nomina(self):
        non_nomina = CfdiDocumentDTO(uuid="x", tipo_comprobante="I", nomina=None)
        self.assertFalse(A.RuleNomUuidPresente().applies(self._ctx(non_nomina)))
        self.assertTrue(A.RuleNomUuidPresente().applies(self._ctx(self._cfdi())))

    # ----------------- F: contable -----------------
    def test_nom060_poliza_existe(self):
        rule = F.RuleNomPolizaExiste()
        sin = SimpleNamespace(related_move_id=None, company_id=self.company)
        self.assertFalse(self._ok(rule, self._cfdi(), cfdi_record=sin))
        self.assertTrue(self._ok(rule, self._cfdi(), cfdi_record=self._rec_con_move()))

    def test_nom061_publicada(self):
        rule = F.RuleNomPolizaPublicada()
        self.assertTrue(self._ok(rule, self._cfdi(), cfdi_record=self._rec_con_move()))
        self.assertFalse(self._ok(rule, self._cfdi(),
                                  cfdi_record=self._rec_con_move(state="draft")))

    def test_nom062_compania(self):
        rule = F.RuleNomPolizaCompania()
        self.assertTrue(self._ok(rule, self._cfdi(), cfdi_record=self._rec_con_move()))
        other = self.env["res.company"].create({"name": "Otra Cia Nomina"})
        self.assertFalse(self._ok(rule, self._cfdi(),
                                  cfdi_record=self._rec_con_move(company_id=other)))

    def test_nom063_periodo(self):
        rule = F.RuleNomPolizaPeriodo()
        self.assertTrue(self._ok(rule, self._cfdi(),
                                 cfdi_record=self._rec_con_move(date=date(2026, 5, 20))))
        self.assertFalse(self._ok(rule, self._cfdi(),
                                  cfdi_record=self._rec_con_move(date=date(2026, 3, 1))))

    def test_nom064_importe(self):
        rule = F.RuleNomPolizaImporte()
        self.assertTrue(self._ok(rule, self._cfdi(),
                                 cfdi_record=self._rec_con_move(amount_total=8000.0)))
        self.assertFalse(self._ok(rule, self._cfdi(),
                                  cfdi_record=self._rec_con_move(amount_total=7000.0)))

    def test_f_applies_requiere_move(self):
        no_move = SimpleNamespace(related_move_id=None, company_id=self.company)
        self.assertFalse(F.RuleNomPolizaPublicada().applies(
            self._ctx(self._cfdi(), cfdi_record=no_move)))
        self.assertTrue(F.RuleNomPolizaPublicada().applies(
            self._ctx(self._cfdi(), cfdi_record=self._rec_con_move())))

    # ----------------- default_enabled (A on / F off) -----------------
    def test_default_enabled_a_on_f_off(self):
        self.Rule._sync_from_registry()
        a = self.Rule.search([("code", "=", "NOM_001_UUID_PRESENTE")])
        f = self.Rule.search([("code", "=", "NOM_060_POLIZA_EXISTE")])
        self.assertTrue(a.default_enabled)
        self.assertFalse(f.default_enabled)
