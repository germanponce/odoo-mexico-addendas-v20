# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
"""Reglas D: cruce del CFDI de nomina contra el RECIBO (hr.payslip).

Codigos NOM_040..NOM_045. OPT-IN + soft-dependency. Comparaciones de importes con
tolerancia configurable; las que no tienen dato comparable se omiten suavemente.
"""
from __future__ import annotations

from decimal import Decimal

from ...base_rule import cfdi_rule
from ._base import RuleResult, SEV_HIGH, SEV_MEDIUM
from ._hr import (
    _NominaConEmpleado, _NominaConRecibo,
    find_employee, find_payslip, payslip_net, field_value,
)

_SAT_REF = "Cruce recibo de nomina (hr.payslip)"

_PERCEP_FIELDS = ("l10n_mx_total_percepciones", "total_percepciones", "total_gross")
_DEDUC_FIELDS = ("l10n_mx_total_deducciones", "total_deducciones", "total_deductions")


@cfdi_rule
class RuleNomReciboExiste(_NominaConEmpleado):
    code = "NOM_040_RECIBO_EXISTE"
    name = "Nomina: existe recibo (hr.payslip) del periodo"
    description = ("Debe existir un recibo de nomina (hr.payslip) del empleado cuyo "
                   "periodo solape el del CFDI. Opt-in: solo si se calcula nomina en Odoo.")
    default_severity = SEV_HIGH
    sat_reference = _SAT_REF

    def execute(self, ctx):
        emp = find_employee(ctx)
        slip = find_payslip(ctx, emp)
        if slip:
            return RuleResult(True, "Recibo localizado (%s)" % slip.number if "number" in slip._fields
                              else "Recibo localizado", score_impact=2)
        return RuleResult(
            False, "No se encontro recibo de nomina para el periodo del CFDI",
            details=self.evidence(empleado=emp.display_name,
                                  valor_xml="%s..%s" % (ctx.cfdi.nomina.fecha_inicial_pago,
                                                        ctx.cfdi.nomina.fecha_final_pago)),
            score_impact=-15)


@cfdi_rule
class RuleNomReciboEstado(_NominaConRecibo):
    code = "NOM_041_RECIBO_ESTADO"
    name = "Nomina: el recibo esta confirmado/pagado"
    description = "El recibo (hr.payslip) deberia estar en estado Hecho (done) o Pagado."
    default_severity = SEV_MEDIUM
    sat_reference = _SAT_REF

    def execute(self, ctx):
        slip = find_payslip(ctx, find_employee(ctx))
        if slip.state in ("done", "paid"):
            return RuleResult(True, "Recibo en estado %s" % slip.state, score_impact=1)
        return RuleResult(
            False, "Recibo en estado '%s' (no confirmado)" % slip.state,
            details=self.evidence(valor_odoo=slip.state), score_impact=-6)


@cfdi_rule
class RuleNomReciboNeto(_NominaConRecibo):
    code = "NOM_042_RECIBO_NETO"
    name = "Nomina: el neto del recibo coincide con el XML"
    description = ("El neto del recibo (hr.payslip) debe coincidir con el Total del "
                   "CFDI de nomina, con tolerancia configurable. Se omite si el recibo "
                   "no expone un neto comparable.")
    default_severity = SEV_HIGH
    sat_reference = _SAT_REF

    def execute(self, ctx):
        slip = find_payslip(ctx, find_employee(ctx))
        net = payslip_net(slip)
        if net is None:
            return RuleResult(True, "Sin neto comparable en el recibo", score_impact=0)
        tol = self.tolerance(ctx, "0.01")
        xml_total = ctx.cfdi.total
        diff = abs(xml_total - net)
        if diff <= tol:
            return RuleResult(True, "Neto del recibo coincide con el XML", score_impact=2)
        return RuleResult(
            False, "Neto XML (%s) distinto al del recibo (%s)" % (xml_total, net),
            details=self.evidence(valor_xml=str(xml_total), valor_odoo=str(net),
                                  diferencia=str(diff)),
            score_impact=-12)


@cfdi_rule
class RuleNomReciboPercepciones(_NominaConRecibo):
    code = "NOM_043_RECIBO_PERCEPCIONES"
    name = "Nomina: total de percepciones coincide con el recibo"
    description = ("El TotalPercepciones del XML deberia coincidir con el del recibo. "
                   "Se omite si el recibo no expone ese total.")
    default_severity = SEV_MEDIUM
    sat_reference = _SAT_REF

    def execute(self, ctx):
        slip = find_payslip(ctx, find_employee(ctx))
        fname, val = field_value(slip, _PERCEP_FIELDS)
        if fname is None:
            return RuleResult(True, "Sin total de percepciones comparable", score_impact=0)
        tol = self.tolerance(ctx, "0.01")
        xml_val = ctx.cfdi.nomina.total_percepciones
        diff = abs(xml_val - Decimal(str(val or 0)))
        if diff <= tol:
            return RuleResult(True, "Total de percepciones coincide", score_impact=1)
        return RuleResult(
            False, "Percepciones XML (%s) distintas al recibo (%s)" % (xml_val, val),
            details=self.evidence(valor_xml=str(xml_val), valor_odoo=str(val),
                                  diferencia=str(diff)),
            score_impact=-6)


@cfdi_rule
class RuleNomReciboDeducciones(_NominaConRecibo):
    code = "NOM_044_RECIBO_DEDUCCIONES"
    name = "Nomina: total de deducciones coincide con el recibo"
    description = ("El TotalDeducciones del XML deberia coincidir con el del recibo. "
                   "Se omite si el recibo no expone ese total.")
    default_severity = SEV_MEDIUM
    sat_reference = _SAT_REF

    def execute(self, ctx):
        slip = find_payslip(ctx, find_employee(ctx))
        fname, val = field_value(slip, _DEDUC_FIELDS)
        if fname is None:
            return RuleResult(True, "Sin total de deducciones comparable", score_impact=0)
        tol = self.tolerance(ctx, "0.01")
        xml_val = ctx.cfdi.nomina.total_deducciones
        diff = abs(xml_val - Decimal(str(val or 0)))
        if diff <= tol:
            return RuleResult(True, "Total de deducciones coincide", score_impact=1)
        return RuleResult(
            False, "Deducciones XML (%s) distintas al recibo (%s)" % (xml_val, val),
            details=self.evidence(valor_xml=str(xml_val), valor_odoo=str(val),
                                  diferencia=str(diff)),
            score_impact=-6)


@cfdi_rule
class RuleNomReciboEmpleado(_NominaConRecibo):
    code = "NOM_045_RECIBO_EMPLEADO"
    name = "Nomina: el empleado del recibo coincide"
    description = "El empleado del recibo debe ser el mismo que casa con el receptor del CFDI."
    default_severity = SEV_HIGH
    sat_reference = _SAT_REF

    def execute(self, ctx):
        emp = find_employee(ctx)
        slip = find_payslip(ctx, emp)
        slip_emp = getattr(slip, "employee_id", None)
        if slip_emp is None:
            return RuleResult(True, "Sin empleado en el recibo para comparar", score_impact=0)
        if getattr(slip_emp, "id", None) == getattr(emp, "id", None):
            return RuleResult(True, "El empleado del recibo coincide", score_impact=1)
        return RuleResult(
            False, "El empleado del recibo no coincide con el receptor del CFDI",
            details=self.evidence(valor_xml=emp.display_name,
                                  valor_odoo=getattr(slip_emp, "display_name", str(slip_emp))),
            score_impact=-12)
