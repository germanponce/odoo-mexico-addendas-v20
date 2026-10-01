# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
"""Reglas F: cruce CONTABLE del CFDI de nomina contra account.move (poliza).

Codigos NOM_060..NOM_064. Usa ``ctx.cfdi_record.related_move_id`` (vinculo ya
existente en el modulo). NOM_060 verifica que exista poliza; las demas solo
aplican cuando hay poliza vinculada (no doble-marcan la ausencia).

Nota: para nominas con poliza por LOTE (un solo asiento para varios empleados),
el cruce de importe (NOM_064) debe afinarse o deshabilitarse por profile; se
refinara en Etapa 2 con el cruce contra hr.payslip.run.
"""
from __future__ import annotations

from decimal import Decimal

from ...base_rule import cfdi_rule
from ._base import BaseNominaRule, RuleResult, SEV_CRITICAL, SEV_HIGH, SEV_MEDIUM

_SAT_REF = "Cruce contable nomina (account.move)"


def _move(ctx):
    return getattr(ctx.cfdi_record, "related_move_id", None)


class _NominaConPoliza(BaseNominaRule):
    """Base de reglas F que solo corren cuando hay poliza vinculada."""
    # Opt-in: solo para clientes que contabilizan la nomina en Odoo. En clientes
    # que solo descargan los XML del SAT (sin nomina en Odoo) el cruce contable
    # no aplica y no debe generar ruido. Las validaciones internas (A) si corren.
    default_enabled = False

    def applies(self, ctx) -> bool:
        return super().applies(ctx) and bool(_move(ctx))


@cfdi_rule
class RuleNomPolizaExiste(BaseNominaRule):
    code = "NOM_060_POLIZA_EXISTE"
    name = "Nomina: existe poliza contable asociada"
    description = ("El CFDI de nomina debe estar vinculado a una poliza "
                   "(account.move). Sin poliza no hay registro contable del gasto. "
                   "Opt-in: encender solo si el cliente contabiliza nomina en Odoo.")
    default_severity = SEV_CRITICAL
    default_enabled = False
    sat_reference = _SAT_REF

    def execute(self, ctx):
        move = _move(ctx)
        if move:
            return RuleResult(True, "Poliza contable vinculada (%s)" % move.name,
                              score_impact=2)
        return RuleResult(
            False, "CFDI de nomina sin poliza contable asociada",
            details=self.evidence(valor_xml=ctx.cfdi.uuid, valor_odoo=None),
            score_impact=-25)


@cfdi_rule
class RuleNomPolizaPublicada(_NominaConPoliza):
    code = "NOM_061_POLIZA_PUBLICADA"
    name = "Nomina: poliza publicada"
    description = "La poliza vinculada al CFDI de nomina debe estar publicada (posted)."
    default_severity = SEV_HIGH
    sat_reference = _SAT_REF

    def execute(self, ctx):
        move = _move(ctx)
        if move.state == "posted":
            return RuleResult(True, "Poliza publicada", score_impact=2)
        return RuleResult(
            False, "Poliza vinculada no publicada (estado: %s)" % move.state,
            details=self.evidence(valor_odoo=move.state, poliza=move.name),
            score_impact=-15)


@cfdi_rule
class RuleNomPolizaCompania(_NominaConPoliza):
    code = "NOM_062_POLIZA_COMPANIA"
    name = "Nomina: la compania de la poliza coincide"
    description = "La poliza debe pertenecer a la misma compania del CFDI de nomina."
    default_severity = SEV_HIGH
    sat_reference = _SAT_REF

    def execute(self, ctx):
        move = _move(ctx)
        doc_company = ctx.cfdi_record.company_id
        if move.company_id == doc_company:
            return RuleResult(True, "Compania coincide", score_impact=1)
        return RuleResult(
            False, "La compania de la poliza no coincide con la del CFDI",
            details=self.evidence(valor_xml=doc_company.display_name,
                                  valor_odoo=move.company_id.display_name,
                                  poliza=move.name),
            score_impact=-15)


@cfdi_rule
class RuleNomPolizaPeriodo(_NominaConPoliza):
    code = "NOM_063_POLIZA_PERIODO"
    name = "Nomina: el periodo contable coincide"
    description = ("El mes/anio de la fecha contable de la poliza debe coincidir "
                   "con la FechaPago del CFDI de nomina.")
    default_severity = SEV_MEDIUM
    sat_reference = _SAT_REF

    def execute(self, ctx):
        move = _move(ctx)
        fp = ctx.cfdi.nomina.fecha_pago
        if not fp or not move.date:
            return RuleResult(True, "Sin fecha para comparar periodo", score_impact=0)
        xml_per = (fp.year, fp.month)
        move_per = (move.date.year, move.date.month)
        if xml_per == move_per:
            return RuleResult(True, "Periodo contable coincide", score_impact=1)
        return RuleResult(
            False, "Periodo de la poliza (%04d-%02d) distinto a FechaPago (%04d-%02d)"
            % (move_per[0], move_per[1], xml_per[0], xml_per[1]),
            details=self.evidence(valor_xml="%04d-%02d" % xml_per,
                                  valor_odoo="%04d-%02d" % move_per,
                                  poliza=move.name),
            score_impact=-8)


@cfdi_rule
class RuleNomPolizaImporte(_NominaConPoliza):
    code = "NOM_064_POLIZA_IMPORTE"
    name = "Nomina: el importe neto coincide con la poliza"
    description = ("El Total (neto) del CFDI de nomina debe coincidir con el "
                   "importe de la poliza, con tolerancia configurable (0.01 MXN). "
                   "Para polizas por lote, deshabilitar o afinar por profile.")
    default_severity = SEV_HIGH
    sat_reference = _SAT_REF

    def execute(self, ctx):
        move = _move(ctx)
        tol = self.tolerance(ctx, "0.01")
        xml_total = ctx.cfdi.total
        move_total = Decimal(str(move.amount_total or 0))
        diff = abs(xml_total - move_total)
        if diff <= tol:
            return RuleResult(True, "Importe neto coincide con la poliza",
                              score_impact=2)
        return RuleResult(
            False, "Neto CFDI (%s) distinto al importe de la poliza (%s)"
            % (xml_total, move_total),
            details=self.evidence(valor_xml=str(xml_total),
                                  valor_odoo=str(move_total),
                                  diferencia=str(diff), poliza=move.name),
            score_impact=-15)
