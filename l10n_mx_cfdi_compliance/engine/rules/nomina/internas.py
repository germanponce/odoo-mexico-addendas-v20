# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
"""Reglas A: validaciones INTERNAS del XML de Nomina (sin cruce con Odoo).

Codigos NOM_001..NOM_016. Severidades mapeadas (ver _base):
Critical->error, High->authorization, Medium->warning.

El XML es la verdad fiscal: estas reglas NO recalculan ni corrigen, solo
verifican consistencia interna y reportan evidencia (valor_xml).
"""
from __future__ import annotations

import re
from decimal import Decimal

from ...base_rule import cfdi_rule
from ._base import BaseNominaRule, RuleResult, SEV_CRITICAL, SEV_HIGH, SEV_MEDIUM
from ._catalogos import is_valid

_UUID_RE = re.compile(
    r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$"
)
_SAT_REF = "Anexo 20 / Guia de llenado Complemento de Nomina 1.2"


# ─────────────────────────── Identificacion (1-7) ───────────────────────────
@cfdi_rule
class RuleNomUuidPresente(BaseNominaRule):
    code = "NOM_001_UUID_PRESENTE"
    name = "Nomina: UUID presente"
    description = "El CFDI de nomina debe tener Folio Fiscal (UUID) del Timbre."
    default_severity = SEV_HIGH
    sat_reference = _SAT_REF

    def execute(self, ctx):
        uuid = ctx.cfdi.uuid
        if uuid:
            return RuleResult(True, "UUID presente", score_impact=1)
        return RuleResult(False, "CFDI de nomina sin UUID",
                          details=self.evidence(valor_xml=uuid), score_impact=-15)


@cfdi_rule
class RuleNomUuidValido(BaseNominaRule):
    code = "NOM_002_UUID_VALIDO"
    name = "Nomina: UUID con formato valido"
    description = "El UUID debe cumplir el formato 8-4-4-4-12 hexadecimal."
    default_severity = SEV_HIGH
    sat_reference = _SAT_REF

    def execute(self, ctx):
        uuid = ctx.cfdi.uuid or ""
        if _UUID_RE.match(uuid):
            return RuleResult(True, "UUID con formato valido", score_impact=1)
        return RuleResult(False, "UUID con formato invalido",
                          details=self.evidence(valor_xml=uuid), score_impact=-15)


@cfdi_rule
class RuleNomRfcEmisor(BaseNominaRule):
    code = "NOM_003_RFC_EMISOR"
    name = "Nomina: RFC emisor (patron) presente"
    description = "El CFDI de nomina debe declarar el RFC del emisor (patron)."
    default_severity = SEV_HIGH
    sat_reference = _SAT_REF

    def execute(self, ctx):
        rfc = ctx.cfdi.rfc_emisor
        if rfc:
            return RuleResult(True, "RFC emisor presente", score_impact=1)
        return RuleResult(False, "CFDI de nomina sin RFC emisor",
                          details=self.evidence(valor_xml=rfc), score_impact=-15)


@cfdi_rule
class RuleNomRfcReceptor(BaseNominaRule):
    code = "NOM_004_RFC_RECEPTOR"
    name = "Nomina: RFC receptor (empleado) presente"
    description = "El CFDI de nomina debe declarar el RFC del receptor (empleado)."
    default_severity = SEV_HIGH
    sat_reference = _SAT_REF

    def execute(self, ctx):
        rfc = ctx.cfdi.rfc_receptor
        if rfc:
            return RuleResult(True, "RFC receptor presente", score_impact=1)
        return RuleResult(False, "CFDI de nomina sin RFC receptor",
                          details=self.evidence(valor_xml=rfc), score_impact=-15)


@cfdi_rule
class RuleNomCurpPresente(BaseNominaRule):
    code = "NOM_005_CURP_PRESENTE"
    name = "Nomina: CURP del empleado presente"
    description = "El nodo Receptor de nomina debe incluir la CURP del empleado."
    default_severity = SEV_MEDIUM
    sat_reference = _SAT_REF

    def execute(self, ctx):
        curp = ctx.cfdi.nomina.curp
        if curp:
            return RuleResult(True, "CURP presente", score_impact=1)
        return RuleResult(False, "Nomina sin CURP del empleado",
                          details=self.evidence(valor_xml=curp), score_impact=-8)


@cfdi_rule
class RuleNomNssPresente(BaseNominaRule):
    code = "NOM_006_NSS_PRESENTE"
    name = "Nomina: NSS del empleado presente"
    description = ("El Numero de Seguridad Social debe estar presente en nomina "
                   "ordinaria de trabajadores (regimen sueldos).")
    default_severity = SEV_MEDIUM
    sat_reference = _SAT_REF

    def execute(self, ctx):
        nss = ctx.cfdi.nomina.nss
        if nss:
            return RuleResult(True, "NSS presente", score_impact=1)
        return RuleResult(False, "Nomina sin NSS del empleado",
                          details=self.evidence(valor_xml=nss), score_impact=-8)


@cfdi_rule
class RuleNomNumEmpleado(BaseNominaRule):
    code = "NOM_007_NUM_EMPLEADO"
    name = "Nomina: NumEmpleado presente"
    description = "El nodo Receptor de nomina debe incluir el numero de empleado."
    default_severity = SEV_MEDIUM
    sat_reference = _SAT_REF

    def execute(self, ctx):
        num = ctx.cfdi.nomina.num_empleado
        if num:
            return RuleResult(True, "NumEmpleado presente", score_impact=1)
        return RuleResult(False, "Nomina sin NumEmpleado",
                          details=self.evidence(valor_xml=num), score_impact=-8)


# ─────────────────────────── Periodo (8-10) ───────────────────────────
@cfdi_rule
class RuleNomFechasPeriodo(BaseNominaRule):
    code = "NOM_008_FECHAS_PERIODO"
    name = "Nomina: FechaInicialPago <= FechaFinalPago"
    description = "El periodo de pago debe ser coherente (inicio no posterior al fin)."
    default_severity = SEV_HIGH
    sat_reference = _SAT_REF

    def execute(self, ctx):
        n = ctx.cfdi.nomina
        fi, ff = n.fecha_inicial_pago, n.fecha_final_pago
        if fi and ff and fi > ff:
            return RuleResult(
                False, "FechaInicialPago posterior a FechaFinalPago",
                details=self.evidence(valor_xml="%s .. %s" % (fi, ff)),
                score_impact=-15)
        return RuleResult(True, "Periodo de pago coherente", score_impact=1)


@cfdi_rule
class RuleNomFechaPagoEnPeriodo(BaseNominaRule):
    code = "NOM_009_FECHA_PAGO_PERIODO"
    name = "Nomina: FechaPago coherente con el periodo"
    description = ("La FechaPago no debe ser anterior al inicio del periodo "
                   "(FechaPago >= FechaInicialPago).")
    default_severity = SEV_MEDIUM
    sat_reference = _SAT_REF

    def execute(self, ctx):
        n = ctx.cfdi.nomina
        fp, fi = n.fecha_pago, n.fecha_inicial_pago
        if fp and fi and fp < fi:
            return RuleResult(
                False, "FechaPago anterior al inicio del periodo",
                details=self.evidence(valor_xml="pago=%s inicio=%s" % (fp, fi)),
                score_impact=-8)
        return RuleResult(True, "FechaPago coherente con el periodo", score_impact=1)


@cfdi_rule
class RuleNomNumDiasPagados(BaseNominaRule):
    code = "NOM_010_NUM_DIAS_PAGADOS"
    name = "Nomina: NumDiasPagados > 0"
    description = "El numero de dias pagados debe ser mayor a cero."
    default_severity = SEV_MEDIUM
    sat_reference = _SAT_REF

    def execute(self, ctx):
        dias = ctx.cfdi.nomina.num_dias_pagados
        if dias > 0:
            return RuleResult(True, "NumDiasPagados > 0", score_impact=1)
        return RuleResult(False, "NumDiasPagados no es mayor a cero",
                          details=self.evidence(valor_xml=dias), score_impact=-8)


# ─────────────────────────── Importes (11-14) ───────────────────────────
@cfdi_rule
class RuleNomTotalPercepciones(BaseNominaRule):
    code = "NOM_011_TOTAL_PERCEPCIONES"
    name = "Nomina: TotalPercepciones >= 0"
    description = "El total de percepciones no puede ser negativo."
    default_severity = SEV_HIGH
    sat_reference = _SAT_REF

    def execute(self, ctx):
        v = ctx.cfdi.nomina.total_percepciones
        if v >= 0:
            return RuleResult(True, "TotalPercepciones valido", score_impact=1)
        return RuleResult(False, "TotalPercepciones negativo",
                          details=self.evidence(valor_xml=v), score_impact=-15)


@cfdi_rule
class RuleNomTotalDeducciones(BaseNominaRule):
    code = "NOM_012_TOTAL_DEDUCCIONES"
    name = "Nomina: TotalDeducciones >= 0"
    description = "El total de deducciones no puede ser negativo."
    default_severity = SEV_HIGH
    sat_reference = _SAT_REF

    def execute(self, ctx):
        v = ctx.cfdi.nomina.total_deducciones
        if v >= 0:
            return RuleResult(True, "TotalDeducciones valido", score_impact=1)
        return RuleResult(False, "TotalDeducciones negativo",
                          details=self.evidence(valor_xml=v), score_impact=-15)


@cfdi_rule
class RuleNomTotalOtrosPagos(BaseNominaRule):
    code = "NOM_013_TOTAL_OTROS_PAGOS"
    name = "Nomina: TotalOtrosPagos >= 0"
    description = "El total de otros pagos no puede ser negativo."
    default_severity = SEV_HIGH
    sat_reference = _SAT_REF

    def execute(self, ctx):
        v = ctx.cfdi.nomina.total_otros_pagos
        if v >= 0:
            return RuleResult(True, "TotalOtrosPagos valido", score_impact=1)
        return RuleResult(False, "TotalOtrosPagos negativo",
                          details=self.evidence(valor_xml=v), score_impact=-15)


@cfdi_rule
class RuleNomNetoCuadra(BaseNominaRule):
    code = "NOM_014_NETO_CUADRA"
    name = "Nomina: Percepciones - Deducciones + OtrosPagos = Total"
    description = ("El neto del complemento (TotalPercepciones - TotalDeducciones "
                   "+ TotalOtrosPagos) debe coincidir con el Total del Comprobante.")
    default_severity = SEV_HIGH
    sat_reference = _SAT_REF

    def execute(self, ctx):
        n = ctx.cfdi.nomina
        neto = n.neto
        total = ctx.cfdi.total
        tol = self.tolerance(ctx, "0.01")
        diff = abs(neto - total)
        if diff <= tol:
            return RuleResult(True, "Neto cuadra con el Total del comprobante",
                              score_impact=2)
        return RuleResult(
            False,
            "Neto calculado (%s) no coincide con Total (%s)" % (neto, total),
            details=self.evidence(valor_xml=str(total), valor_odoo=str(neto),
                                  diferencia=str(diff),
                                  detalle="neto = percepciones - deducciones + otros_pagos"),
            score_impact=-15)


# ─────────────────────────── Catalogos (15) ───────────────────────────
@cfdi_rule
class RuleNomCatalogos(BaseNominaRule):
    code = "NOM_015_CATALOGOS_SAT"
    name = "Nomina: codigos en catalogos SAT validos"
    description = ("Valida TipoContrato, TipoJornada, TipoRegimen, RiesgoPuesto, "
                   "TipoPercepcion, TipoDeduccion y TipoOtroPago contra los "
                   "catalogos SAT de nomina 1.2.")
    default_severity = SEV_MEDIUM
    sat_reference = _SAT_REF + " (catalogos c_*)"

    def execute(self, ctx):
        n = ctx.cfdi.nomina
        invalid = []

        def chk(cat, code):
            if code and not is_valid(cat, code):
                invalid.append({"catalogo": cat, "codigo": code})

        chk("TipoNomina", n.tipo_nomina)
        chk("TipoContrato", n.tipo_contrato)
        chk("TipoJornada", n.tipo_jornada)
        chk("TipoRegimen", n.tipo_regimen)
        chk("RiesgoPuesto", n.riesgo_puesto)
        for p in n.percepciones:
            chk("TipoPercepcion", p.tipo_percepcion)
        for d in n.deducciones:
            chk("TipoDeduccion", d.tipo_deduccion)
        for o in n.otros_pagos:
            chk("TipoOtroPago", o.tipo_otro_pago)

        if invalid:
            return RuleResult(
                False, "Codigos fuera de catalogo SAT: %d" % len(invalid),
                details={"invalidos": invalid}, score_impact=-8)
        return RuleResult(True, "Catalogos SAT validos", score_impact=1)


# ─────────────────────────── Horas extra (16) ───────────────────────────
@cfdi_rule
class RuleNomHorasExtra(BaseNominaRule):
    code = "NOM_016_HORAS_EXTRA"
    name = "Nomina: horas extra con datos validos"
    description = ("Cuando hay HorasExtra: HorasExtra>0, Dias>0 y TipoHoras valido "
                   "(01 Dobles, 02 Triples, 03 Simples).")
    default_severity = SEV_MEDIUM
    sat_reference = _SAT_REF

    def execute(self, ctx):
        n = ctx.cfdi.nomina
        issues = []
        for p in n.percepciones:
            for he in p.horas_extra:
                if he.horas_extra <= 0:
                    issues.append({"clave": p.clave, "campo": "HorasExtra",
                                   "valor": he.horas_extra})
                if he.dias <= 0:
                    issues.append({"clave": p.clave, "campo": "Dias",
                                   "valor": he.dias})
                if not is_valid("TipoHoras", he.tipo_horas):
                    issues.append({"clave": p.clave, "campo": "TipoHoras",
                                   "valor": he.tipo_horas})
        if issues:
            return RuleResult(
                False, "Horas extra con datos invalidos: %d" % len(issues),
                details={"issues": issues}, score_impact=-8)
        return RuleResult(True, "Horas extra validas o ausentes", score_impact=1)
