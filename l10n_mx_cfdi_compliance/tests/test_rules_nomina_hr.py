# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
"""Pruebas de las reglas de Nomina Etapa 2 — cruces vs RRHH (B empleado, C contrato).

Estrategia sin dependencia de hr_payroll: la LOGICA de cada regla se prueba
pre-sembrando el match en ``ctx.scratchpad`` (las reglas leen el cache primero,
ver _hr.find_*), con un recordset mock minimo. El SOFT-OMIT (modulo hr ausente)
se prueba con un ``env`` stub cuyo ``get`` devuelve None. Las reglas D/E (recibo,
lote) se agregan en la Fase 2b.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from .common import CfdiComplianceCommon
from odoo.addons.l10n_mx_cfdi_compliance.engine.context import CfdiValidationContext
from odoo.addons.l10n_mx_cfdi_compliance.engine.parser.cfdi_parser import CfdiDocumentDTO
from odoo.addons.l10n_mx_cfdi_compliance.engine.parser.complementos.nomina12 import (
    NominaDTO, NominaPercepcion, NominaDeduccion, NominaOtroPago,
)
from odoo.addons.l10n_mx_cfdi_compliance.engine.rules.nomina import empleado as B
from odoo.addons.l10n_mx_cfdi_compliance.engine.rules.nomina import contrato as C
from odoo.addons.l10n_mx_cfdi_compliance.engine.rules.nomina import recibo as D
from odoo.addons.l10n_mx_cfdi_compliance.engine.rules.nomina import lote as E
from odoo.addons.l10n_mx_cfdi_compliance.engine.rules.nomina import _hr

_UNSET = object()


class _Rec:
    """Mock minimo de un recordset Odoo de 1 registro (sin instalar hr).

    Soporta ``rec._fields`` (membership), ``rec.attr`` y ``rec['attr']``, y es
    truthy. Sirve para empleado/contrato/recibo simulados.
    """

    def __init__(self, **kw):
        object.__setattr__(self, "_data", kw)

    @property
    def _fields(self):
        return object.__getattribute__(self, "_data")

    def __getattr__(self, name):
        data = object.__getattribute__(self, "_data")
        if name in data:
            return data[name]
        raise AttributeError(name)

    def __getitem__(self, name):
        return object.__getattribute__(self, "_data")[name]

    def __bool__(self):
        return True


class TestRulesNominaHr(CfdiComplianceCommon):

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
            tipo_contrato="01", tipo_jornada="01", periodicidad_pago="04",
            salario_base_cot_apor=Decimal("300"),
            salario_diario_integrado=Decimal("310"),
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

    def _rec(self, **kw):
        base = dict(rfc_receptor="XAXX010101000", company_id=self.company)
        base.update(kw)
        return SimpleNamespace(**base)

    def _ctx(self, cfdi=None, rec=None, env=None, emp=_UNSET, contract=_UNSET,
             payslip=_UNSET):
        """Contexto con scratchpad pre-sembrado para forzar el match deseado."""
        ctx = CfdiValidationContext(
            env=env if env is not None else self.env,
            company=self.company,
            cfdi_record=rec if rec is not None else self._rec(),
            cfdi=cfdi if cfdi is not None else self._cfdi(),
            profile=self.profile)
        if emp is not _UNSET:
            ctx.scratchpad["nom_employee"] = emp
        if contract is not _UNSET:
            ctx.scratchpad["nom_contract"] = contract
        if payslip is not _UNSET:
            ctx.scratchpad["nom_payslip"] = payslip
        return ctx

    def _emp(self, **kw):
        base = dict(id=1, display_name="Juan Perez", active=True,
                    l10n_mx_rfc="XAXX010101000", l10n_mx_curp="XEXX010101HNEXXXA4",
                    l10n_mx_nss="12345678901")
        base.update(kw)
        return _Rec(**base)

    def _contract(self, **kw):
        base = dict(id=1, name="CT/EMP001", date_start=date(2026, 1, 1),
                    date_end=False, state="open", schedule_pay="semi-monthly",
                    l10n_mx_sbc=Decimal("300"), l10n_mx_sdi=Decimal("310"),
                    l10n_mx_tipo_contrato="01")
        base.update(kw)
        return _Rec(**base)

    def _run(self, **kw):
        base = dict(id=1, name="LOTE/2026/05", date_start=date(2026, 5, 1),
                    date_end=date(2026, 5, 15), slip_ids=[])
        base.update(kw)
        return _Rec(**base)

    def _payslip(self, **kw):
        base = dict(id=1, number="SLIP/001", state="done",
                    net_wage=Decimal("8000"), employee_id=self._emp(),
                    total_percepciones=Decimal("10000"),
                    total_deducciones=Decimal("2500"),
                    payslip_run_id=self._run())
        base.update(kw)
        return _Rec(**base)

    def _move(self, **kw):
        base = dict(amount_total=8000.0, name="AJ/2026/05")
        base.update(kw)
        return SimpleNamespace(**base)

    # =================== helpers (_hr) ===================
    def test_norm_y_field_value(self):
        self.assertEqual(_hr._norm("  xaxx010101000 "), "XAXX010101000")
        rec = self._emp()
        self.assertEqual(_hr.field_value(rec, _hr._RFC_FIELDS),
                         ("l10n_mx_rfc", "XAXX010101000"))
        self.assertEqual(_hr.field_value(rec, ("inexistente",)), (None, None))

    def test_find_employee_usa_cache(self):
        emp = self._emp()
        ctx = self._ctx(emp=emp)
        self.assertIs(_hr.find_employee(ctx), emp)

    def test_profile_param(self):
        # Sin config -> default
        self.assertEqual(_hr.profile_param(self._ctx(), "x", "def"), "def")

    def test_payslip_net_campo_directo(self):
        slip = _Rec(net_wage=Decimal("8000"))
        self.assertEqual(_hr.payslip_net(slip), Decimal("8000"))

    def test_payslip_net_lineas(self):
        line = SimpleNamespace(code="NET", total=8000.0)
        slip = _Rec(line_ids=[line])
        self.assertEqual(_hr.payslip_net(slip), Decimal("8000"))

    # =================== soft-omit (sin hr) ===================
    def test_softomit_sin_hr(self):
        env_no_hr = SimpleNamespace(get=lambda m: None)
        ctx = self._ctx(env=env_no_hr)
        for rule in (B.RuleNomEmpleadoExiste(), B.RuleNomEmpleadoCurp(),
                     C.RuleNomContratoVigente(), C.RuleNomContratoSbc()):
            self.assertFalse(rule.applies(ctx),
                             "%s no debe aplicar sin hr" % rule.code)

    def test_applies_con_hr_y_match(self):
        env_hr = SimpleNamespace(get=lambda m: True)  # modelo "presente"
        ctx = self._ctx(env=env_hr, emp=self._emp(), contract=self._contract())
        self.assertTrue(B.RuleNomEmpleadoExiste().applies(ctx))
        self.assertTrue(B.RuleNomEmpleadoCurp().applies(ctx))
        self.assertTrue(C.RuleNomContratoSbc().applies(ctx))

    # =================== B: empleado ===================
    def test_nom020_empleado_existe(self):
        self.assertTrue(B.RuleNomEmpleadoExiste().execute(
            self._ctx(emp=self._emp())).passed)
        self.assertFalse(B.RuleNomEmpleadoExiste().execute(
            self._ctx(emp=_hr_empty())).passed)

    def test_nom021_curp(self):
        self.assertTrue(B.RuleNomEmpleadoCurp().execute(self._ctx(emp=self._emp())).passed)
        bad = self._emp(l10n_mx_curp="OTRA010101HNEXXXA4")
        self.assertFalse(B.RuleNomEmpleadoCurp().execute(self._ctx(emp=bad)).passed)
        # Sin campo CURP -> se omite (pass)
        nocurp = _Rec(id=1, display_name="x", active=True, l10n_mx_rfc="XAXX010101000")
        self.assertTrue(B.RuleNomEmpleadoCurp().execute(self._ctx(emp=nocurp)).passed)

    def test_nom022_nss(self):
        self.assertTrue(B.RuleNomEmpleadoNss().execute(self._ctx(emp=self._emp())).passed)
        bad = self._emp(l10n_mx_nss="99999999999")
        self.assertFalse(B.RuleNomEmpleadoNss().execute(self._ctx(emp=bad)).passed)

    def test_nom023_rfc(self):
        self.assertTrue(B.RuleNomEmpleadoRfc().execute(self._ctx(emp=self._emp())).passed)
        bad = self._emp(l10n_mx_rfc="OTRO010101AAA")
        self.assertFalse(B.RuleNomEmpleadoRfc().execute(self._ctx(emp=bad)).passed)

    def test_nom024_activo(self):
        self.assertTrue(B.RuleNomEmpleadoActivo().execute(self._ctx(emp=self._emp())).passed)
        self.assertFalse(B.RuleNomEmpleadoActivo().execute(
            self._ctx(emp=self._emp(active=False))).passed)

    # =================== C: contrato ===================
    def test_nom030_contrato_vigente(self):
        ok = self._ctx(emp=self._emp(), contract=self._contract())
        self.assertTrue(C.RuleNomContratoVigente().execute(ok).passed)
        # Sin contrato
        self.assertFalse(C.RuleNomContratoVigente().execute(
            self._ctx(emp=self._emp(), contract=_hr_empty())).passed)
        # Contrato que no cubre el periodo (empieza despues)
        tarde = self._contract(date_start=date(2026, 5, 10))
        self.assertFalse(C.RuleNomContratoVigente().execute(
            self._ctx(emp=self._emp(), contract=tarde)).passed)

    def test_nom031_sbc(self):
        self.assertTrue(C.RuleNomContratoSbc().execute(
            self._ctx(emp=self._emp(), contract=self._contract())).passed)
        bad = self._contract(l10n_mx_sbc=Decimal("250"))
        self.assertFalse(C.RuleNomContratoSbc().execute(
            self._ctx(emp=self._emp(), contract=bad)).passed)
        # Sin campo SBC -> se omite
        nosbc = _Rec(id=1, name="c", date_start=date(2026, 1, 1), date_end=False)
        self.assertTrue(C.RuleNomContratoSbc().execute(
            self._ctx(emp=self._emp(), contract=nosbc)).passed)

    def test_nom032_sdi(self):
        self.assertTrue(C.RuleNomContratoSdi().execute(
            self._ctx(emp=self._emp(), contract=self._contract())).passed)
        bad = self._contract(l10n_mx_sdi=Decimal("999"))
        self.assertFalse(C.RuleNomContratoSdi().execute(
            self._ctx(emp=self._emp(), contract=bad)).passed)

    def test_nom033_periodicidad(self):
        self.assertTrue(C.RuleNomContratoPeriodicidad().execute(
            self._ctx(emp=self._emp(), contract=self._contract())).passed)
        bad = self._contract(schedule_pay="monthly")  # XML "04"->semi-monthly
        self.assertFalse(C.RuleNomContratoPeriodicidad().execute(
            self._ctx(emp=self._emp(), contract=bad)).passed)

    def test_nom034_tipo(self):
        self.assertTrue(C.RuleNomContratoTipo().execute(
            self._ctx(emp=self._emp(), contract=self._contract())).passed)
        bad = self._contract(l10n_mx_tipo_contrato="99")
        self.assertFalse(C.RuleNomContratoTipo().execute(
            self._ctx(emp=self._emp(), contract=bad)).passed)

    # =================== D: recibo (hr.payslip) ===================
    def _ctx_d(self, payslip=_UNSET, emp=None, rec=None):
        return self._ctx(emp=emp if emp is not None else self._emp(),
                         payslip=payslip, rec=rec)

    def test_nom040_recibo_existe(self):
        self.assertTrue(D.RuleNomReciboExiste().execute(
            self._ctx_d(payslip=self._payslip())).passed)
        self.assertFalse(D.RuleNomReciboExiste().execute(
            self._ctx_d(payslip=_hr_empty())).passed)

    def test_nom041_estado(self):
        self.assertTrue(D.RuleNomReciboEstado().execute(
            self._ctx_d(payslip=self._payslip())).passed)
        self.assertFalse(D.RuleNomReciboEstado().execute(
            self._ctx_d(payslip=self._payslip(state="draft"))).passed)

    def test_nom042_neto(self):
        self.assertTrue(D.RuleNomReciboNeto().execute(
            self._ctx_d(payslip=self._payslip())).passed)
        self.assertFalse(D.RuleNomReciboNeto().execute(
            self._ctx_d(payslip=self._payslip(net_wage=Decimal("7000")))).passed)
        # Sin neto comparable -> se omite
        nonet = _Rec(id=1, state="done")
        self.assertTrue(D.RuleNomReciboNeto().execute(
            self._ctx_d(payslip=nonet)).passed)

    def test_nom043_percepciones(self):
        self.assertTrue(D.RuleNomReciboPercepciones().execute(
            self._ctx_d(payslip=self._payslip())).passed)
        bad = self._payslip(total_percepciones=Decimal("9999"))
        self.assertFalse(D.RuleNomReciboPercepciones().execute(
            self._ctx_d(payslip=bad)).passed)

    def test_nom044_deducciones(self):
        self.assertTrue(D.RuleNomReciboDeducciones().execute(
            self._ctx_d(payslip=self._payslip())).passed)
        bad = self._payslip(total_deducciones=Decimal("9999"))
        self.assertFalse(D.RuleNomReciboDeducciones().execute(
            self._ctx_d(payslip=bad)).passed)

    def test_nom045_empleado(self):
        emp = self._emp()
        ok = self._ctx(emp=emp, payslip=self._payslip(employee_id=emp))
        self.assertTrue(D.RuleNomReciboEmpleado().execute(ok).passed)
        otro = self._emp(id=999, display_name="Otro")
        self.assertFalse(D.RuleNomReciboEmpleado().execute(
            self._ctx(emp=emp, payslip=self._payslip(employee_id=otro))).passed)

    # =================== E: lote (hr.payslip.run) ===================
    def test_nom050_pertenece(self):
        self.assertTrue(E.RuleNomLotePertenece().execute(
            self._ctx_d(payslip=self._payslip())).passed)
        sin = self._payslip(payslip_run_id=_hr_empty())
        self.assertFalse(E.RuleNomLotePertenece().execute(
            self._ctx_d(payslip=sin)).passed)

    def test_nom051_periodo(self):
        self.assertTrue(E.RuleNomLotePeriodo().execute(
            self._ctx_d(payslip=self._payslip())).passed)
        fuera = self._payslip(payslip_run_id=self._run(
            date_start=date(2026, 1, 1), date_end=date(2026, 1, 15)))
        self.assertFalse(E.RuleNomLotePeriodo().execute(
            self._ctx_d(payslip=fuera)).passed)

    def test_nom052_importe_lote(self):
        # 2 recibos de 4000 c/u = 8000 == poliza 8000 -> pasa
        slips = [_Rec(net_wage=Decimal("4000")), _Rec(net_wage=Decimal("4000"))]
        run = self._run(slip_ids=slips)
        slip = self._payslip(payslip_run_id=run)
        rec = self._rec(related_move_id=self._move(amount_total=8000.0))
        self.assertTrue(E.RuleNomLoteImporte().execute(
            self._ctx(emp=self._emp(), payslip=slip, rec=rec)).passed)
        # poliza 9000 != 8000 -> falla
        rec2 = self._rec(related_move_id=self._move(amount_total=9000.0))
        self.assertFalse(E.RuleNomLoteImporte().execute(
            self._ctx(emp=self._emp(), payslip=slip, rec=rec2)).passed)


def _hr_empty():
    """Recordset 'vacio' simulado: falsy (empleado/contrato no encontrado)."""
    class _Empty:
        def __bool__(self):
            return False
        def __getattr__(self, n):
            return False
    return _Empty()
