# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
"""Reglas C: cruce del CFDI de nomina contra el CONTRATO (hr.contract).

Codigos NOM_030..NOM_034. OPT-IN + soft-dependency. Las comparaciones de datos
(SBC/SDI/periodicidad/tipo) se OMITEN suavemente si el contrato de Odoo no tiene
el campo equivalente (distintos modulos de nomina MX), evitando falsos positivos.
"""
from __future__ import annotations

from decimal import Decimal

from ...base_rule import cfdi_rule
from ._base import RuleResult, SEV_HIGH, SEV_MEDIUM
from ._hr import (
    _NominaConEmpleado, _NominaConContrato,
    find_employee, find_contract, field_value, _SBC_FIELDS, _SDI_FIELDS,
)

_SAT_REF = "Cruce contrato (hr.contract)"

# Mapa best-effort periodicidad SAT -> hr.contract.schedule_pay (Odoo 17+).
_PERIODICIDAD_SCHEDULE = {
    "01": "daily", "02": "weekly", "03": "bi-weekly",
    "04": "semi-monthly", "05": "monthly", "06": "bi-monthly",
}


@cfdi_rule
class RuleNomContratoVigente(_NominaConEmpleado):
    code = "NOM_030_CONTRATO_VIGENTE"
    name = "Nomina: contrato vigente que cubre el periodo"
    description = ("El empleado debe tener un contrato cuyo periodo cubra las "
                   "fechas del CFDI de nomina (FechaInicialPago..FechaFinalPago).")
    default_severity = SEV_HIGH
    sat_reference = _SAT_REF

    def execute(self, ctx):
        emp = find_employee(ctx)
        contract = find_contract(ctx, emp)
        if not contract:
            return RuleResult(
                False, "El empleado no tiene contrato que cubra el periodo",
                details=self.evidence(empleado=emp.display_name,
                                      valor_xml="%s..%s" % (ctx.cfdi.nomina.fecha_inicial_pago,
                                                            ctx.cfdi.nomina.fecha_final_pago)),
                score_impact=-15)
        ini = ctx.cfdi.nomina.fecha_inicial_pago
        fin = ctx.cfdi.nomina.fecha_final_pago
        covers = True
        if ini and fin:
            covers = (contract.date_start and contract.date_start <= ini
                      and (not contract.date_end or contract.date_end >= fin))
        if covers:
            return RuleResult(True, "Contrato vigente cubre el periodo (%s)" % contract.name,
                              score_impact=2)
        return RuleResult(
            False, "El contrato no cubre todo el periodo del CFDI",
            details=self.evidence(
                valor_xml="%s..%s" % (ini, fin),
                valor_odoo="%s..%s" % (contract.date_start, contract.date_end or "abierto"),
                contrato=contract.name),
            score_impact=-8)


@cfdi_rule
class RuleNomContratoSbc(_NominaConContrato):
    code = "NOM_031_CONTRATO_SBC"
    name = "Nomina: el SBC coincide con el contrato"
    description = ("El Salario Base de Cotizacion del XML debe coincidir con el "
                   "del contrato (tolerancia configurable). Se omite si el contrato "
                   "no tiene campo de SBC.")
    default_severity = SEV_MEDIUM
    sat_reference = _SAT_REF

    def execute(self, ctx):
        contract = find_contract(ctx, find_employee(ctx))
        fname, odoo_sbc = field_value(contract, _SBC_FIELDS)
        xml_sbc = ctx.cfdi.nomina.salario_base_cot_apor
        if fname is None or not xml_sbc:
            return RuleResult(True, "Sin SBC comparable", score_impact=0)
        tol = self.tolerance(ctx, "0.01")
        diff = abs(xml_sbc - Decimal(str(odoo_sbc or 0)))
        if diff <= tol:
            return RuleResult(True, "SBC coincide con el contrato", score_impact=1)
        return RuleResult(
            False, "SBC del XML (%s) distinto al del contrato (%s)" % (xml_sbc, odoo_sbc),
            details=self.evidence(valor_xml=str(xml_sbc), valor_odoo=str(odoo_sbc),
                                  diferencia=str(diff), contrato=contract.name),
            score_impact=-6)


@cfdi_rule
class RuleNomContratoSdi(_NominaConContrato):
    code = "NOM_032_CONTRATO_SDI"
    name = "Nomina: el SDI coincide con el contrato"
    description = ("El Salario Diario Integrado del XML debe coincidir con el del "
                   "contrato (tolerancia configurable). Se omite si no hay campo SDI.")
    default_severity = SEV_MEDIUM
    sat_reference = _SAT_REF

    def execute(self, ctx):
        contract = find_contract(ctx, find_employee(ctx))
        fname, odoo_sdi = field_value(contract, _SDI_FIELDS)
        xml_sdi = ctx.cfdi.nomina.salario_diario_integrado
        if fname is None or not xml_sdi:
            return RuleResult(True, "Sin SDI comparable", score_impact=0)
        tol = self.tolerance(ctx, "0.01")
        diff = abs(xml_sdi - Decimal(str(odoo_sdi or 0)))
        if diff <= tol:
            return RuleResult(True, "SDI coincide con el contrato", score_impact=1)
        return RuleResult(
            False, "SDI del XML (%s) distinto al del contrato (%s)" % (xml_sdi, odoo_sdi),
            details=self.evidence(valor_xml=str(xml_sdi), valor_odoo=str(odoo_sdi),
                                  diferencia=str(diff), contrato=contract.name),
            score_impact=-6)


@cfdi_rule
class RuleNomContratoPeriodicidad(_NominaConContrato):
    code = "NOM_033_CONTRATO_PERIODICIDAD"
    name = "Nomina: la periodicidad de pago coincide"
    description = ("La PeriodicidadPago del XML deberia corresponder al schedule_pay "
                   "del contrato. Comparacion best-effort; se omite si no hay mapeo claro.")
    default_severity = SEV_MEDIUM
    sat_reference = _SAT_REF

    def execute(self, ctx):
        contract = find_contract(ctx, find_employee(ctx))
        xml_per = (ctx.cfdi.nomina.periodicidad_pago or "").strip()
        mapped = _PERIODICIDAD_SCHEDULE.get(xml_per)
        if "schedule_pay" not in contract._fields or not mapped or not contract.schedule_pay:
            return RuleResult(True, "Periodicidad no comparable", score_impact=0)
        if contract.schedule_pay == mapped:
            return RuleResult(True, "Periodicidad coincide", score_impact=1)
        return RuleResult(
            False, "Periodicidad XML (%s->%s) distinta al contrato (%s)"
            % (xml_per, mapped, contract.schedule_pay),
            details=self.evidence(valor_xml=mapped, valor_odoo=contract.schedule_pay,
                                  periodicidad_sat=xml_per, contrato=contract.name),
            score_impact=-4)


@cfdi_rule
class RuleNomContratoTipo(_NominaConContrato):
    code = "NOM_034_CONTRATO_TIPO"
    name = "Nomina: el tipo de contrato coincide"
    description = ("El TipoContrato (clave SAT) del XML deberia coincidir con el del "
                   "contrato en Odoo, si el contrato guarda la clave SAT. Se omite si no.")
    default_severity = SEV_MEDIUM
    sat_reference = _SAT_REF

    _TIPO_FIELDS = ("l10n_mx_tipo_contrato", "tipo_contrato", "sat_tipo_contrato")

    def execute(self, ctx):
        contract = find_contract(ctx, find_employee(ctx))
        xml_tipo = (ctx.cfdi.nomina.tipo_contrato or "").strip()
        fname, odoo_tipo = field_value(contract, self._TIPO_FIELDS)
        if not xml_tipo or fname is None or not odoo_tipo:
            return RuleResult(True, "Tipo de contrato no comparable", score_impact=0)
        if str(odoo_tipo).strip() == xml_tipo:
            return RuleResult(True, "Tipo de contrato coincide", score_impact=1)
        return RuleResult(
            False, "Tipo de contrato XML (%s) distinto al de Odoo (%s)" % (xml_tipo, odoo_tipo),
            details=self.evidence(valor_xml=xml_tipo, valor_odoo=str(odoo_tipo),
                                  contrato=contract.name),
            score_impact=-4)
