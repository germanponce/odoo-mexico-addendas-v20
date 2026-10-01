# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
"""Reglas B: cruce del CFDI de nomina contra el EMPLEADO (hr.employee).

Codigos NOM_020..NOM_024. OPT-IN + soft-dependency (ver _hr.py): solo corren si
hr.employee esta instalado; las que comparan un dato se omiten suavemente si el
empleado no tiene ese campo (no marcan falso positivo).
"""
from __future__ import annotations

from ...base_rule import cfdi_rule
from ._base import RuleResult, SEV_HIGH, SEV_MEDIUM
from ._hr import (
    _NominaHrEmpleado, _NominaConEmpleado, find_employee, field_value, _norm,
    _RFC_FIELDS, _CURP_FIELDS, _NSS_FIELDS,
)

_SAT_REF = "Cruce empleado (hr.employee)"


@cfdi_rule
class RuleNomEmpleadoExiste(_NominaHrEmpleado):
    code = "NOM_020_EMPLEADO_EXISTE"
    name = "Nomina: el empleado existe en Odoo"
    description = ("El receptor del CFDI de nomina debe corresponder a un empleado "
                   "(hr.employee) en Odoo, casado por RFC/CURP/NSS/No. de empleado. "
                   "Opt-in: encender solo si el cliente lleva la nomina en Odoo.")
    default_severity = SEV_HIGH
    sat_reference = _SAT_REF

    def execute(self, ctx):
        emp = find_employee(ctx)
        if emp:
            return RuleResult(True, "Empleado localizado: %s" % emp.display_name,
                              details=self.evidence(valor_odoo=emp.display_name),
                              score_impact=2)
        return RuleResult(
            False, "No se encontro empleado para el receptor del CFDI de nomina",
            details=self.evidence(valor_xml=ctx.cfdi_record.rfc_receptor,
                                  curp=ctx.cfdi.nomina.curp,
                                  num_empleado=ctx.cfdi.nomina.num_empleado),
            score_impact=-20)


@cfdi_rule
class RuleNomEmpleadoCurp(_NominaConEmpleado):
    code = "NOM_021_EMPLEADO_CURP"
    name = "Nomina: la CURP coincide con el empleado"
    description = "La CURP del receptor del CFDI debe coincidir con la del empleado."
    default_severity = SEV_HIGH
    sat_reference = _SAT_REF

    def execute(self, ctx):
        emp = find_employee(ctx)
        xml_curp = _norm(ctx.cfdi.nomina.curp)
        fname, odoo_curp = field_value(emp, _CURP_FIELDS)
        if not xml_curp or fname is None:
            return RuleResult(True, "Sin CURP comparable", score_impact=0)
        if _norm(odoo_curp) == xml_curp:
            return RuleResult(True, "CURP coincide", score_impact=1)
        return RuleResult(
            False, "CURP del XML distinta a la del empleado",
            details=self.evidence(valor_xml=xml_curp, valor_odoo=_norm(odoo_curp),
                                  empleado=emp.display_name),
            score_impact=-15)


@cfdi_rule
class RuleNomEmpleadoNss(_NominaConEmpleado):
    code = "NOM_022_EMPLEADO_NSS"
    name = "Nomina: el NSS coincide con el empleado"
    description = "El Numero de Seguridad Social del XML debe coincidir con el del empleado."
    default_severity = SEV_MEDIUM
    sat_reference = _SAT_REF

    def execute(self, ctx):
        xml_nss = (ctx.cfdi.nomina.nss or "").strip()
        emp = find_employee(ctx)
        fname, odoo_nss = field_value(emp, _NSS_FIELDS)
        if not xml_nss or fname is None:
            return RuleResult(True, "Sin NSS comparable", score_impact=0)
        if (odoo_nss or "").strip() == xml_nss:
            return RuleResult(True, "NSS coincide", score_impact=1)
        return RuleResult(
            False, "NSS del XML distinto al del empleado",
            details=self.evidence(valor_xml=xml_nss, valor_odoo=odoo_nss,
                                  empleado=emp.display_name),
            score_impact=-8)


@cfdi_rule
class RuleNomEmpleadoRfc(_NominaConEmpleado):
    code = "NOM_023_EMPLEADO_RFC"
    name = "Nomina: el RFC coincide con el empleado"
    description = "El RFC del receptor del CFDI debe coincidir con el RFC del empleado."
    default_severity = SEV_HIGH
    sat_reference = _SAT_REF

    def execute(self, ctx):
        xml_rfc = _norm(ctx.cfdi_record.rfc_receptor)
        emp = find_employee(ctx)
        fname, odoo_rfc = field_value(emp, _RFC_FIELDS)
        if not xml_rfc or fname is None:
            return RuleResult(True, "Sin RFC comparable", score_impact=0)
        if _norm(odoo_rfc) == xml_rfc:
            return RuleResult(True, "RFC coincide", score_impact=1)
        return RuleResult(
            False, "RFC del XML distinto al del empleado",
            details=self.evidence(valor_xml=xml_rfc, valor_odoo=_norm(odoo_rfc),
                                  empleado=emp.display_name),
            score_impact=-12)


@cfdi_rule
class RuleNomEmpleadoActivo(_NominaConEmpleado):
    code = "NOM_024_EMPLEADO_ACTIVO"
    name = "Nomina: el empleado esta activo"
    description = ("El empleado casado deberia estar activo en la fecha de pago. "
                   "Un CFDI de nomina a un empleado archivado puede indicar error.")
    default_severity = SEV_MEDIUM
    sat_reference = _SAT_REF

    def execute(self, ctx):
        emp = find_employee(ctx)
        if emp.active:
            return RuleResult(True, "Empleado activo", score_impact=1)
        return RuleResult(
            False, "El empleado casado esta archivado/inactivo",
            details=self.evidence(valor_odoo="archivado", empleado=emp.display_name),
            score_impact=-5)
