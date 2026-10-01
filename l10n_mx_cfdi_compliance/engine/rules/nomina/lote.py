# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
"""Reglas E: cruce del CFDI de nomina contra el LOTE de recibos (hr.payslip.run).

Codigos NOM_050..NOM_052. OPT-IN + soft-dependency. NOM_052 refina el cruce de
importe para nominas con POLIZA POR LOTE (un solo asiento para varios empleados):
compara el importe de la poliza contra la SUMA de netos de todos los recibos del
lote, en vez de contra el neto de un solo CFDI (lo que NOM_064 no puede resolver).
"""
from __future__ import annotations

from decimal import Decimal

from ...base_rule import cfdi_rule
from ._base import RuleResult, SEV_HIGH, SEV_MEDIUM
from ._hr import _NominaConRecibo, find_employee, find_payslip, find_run, payslip_net

_SAT_REF = "Cruce lote de nomina (hr.payslip.run)"


class _NominaConLote(_NominaConRecibo):
    """Ademas exige que el recibo pertenezca a un lote (hr.payslip.run)."""

    def applies(self, ctx) -> bool:
        if not super().applies(ctx):
            return False
        slip = find_payslip(ctx, find_employee(ctx))
        return bool(find_run(slip))


@cfdi_rule
class RuleNomLotePertenece(_NominaConRecibo):
    code = "NOM_050_LOTE_PERTENECE"
    name = "Nomina: el recibo pertenece a un lote"
    description = ("El recibo de nomina deberia estar agrupado en un lote "
                   "(hr.payslip.run). Util para conciliar la nomina por corrida.")
    default_severity = SEV_MEDIUM
    sat_reference = _SAT_REF

    def execute(self, ctx):
        slip = find_payslip(ctx, find_employee(ctx))
        run = find_run(slip)
        if run:
            return RuleResult(True, "Recibo en lote (%s)" % run.name, score_impact=1)
        return RuleResult(
            False, "El recibo no pertenece a ningun lote de nomina",
            details=self.evidence(valor_odoo=None), score_impact=-4)


@cfdi_rule
class RuleNomLotePeriodo(_NominaConLote):
    code = "NOM_051_LOTE_PERIODO"
    name = "Nomina: el periodo del lote coincide con la FechaPago"
    description = ("La FechaPago del CFDI debe caer dentro del periodo del lote "
                   "(date_start..date_end). Se omite si el lote no expone fechas.")
    default_severity = SEV_MEDIUM
    sat_reference = _SAT_REF

    def execute(self, ctx):
        run = find_run(find_payslip(ctx, find_employee(ctx)))
        fp = ctx.cfdi.nomina.fecha_pago
        ds = getattr(run, "date_start", None)
        de = getattr(run, "date_end", None)
        if not fp or not ds or not de:
            return RuleResult(True, "Sin fechas de lote comparables", score_impact=0)
        if ds <= fp <= de:
            return RuleResult(True, "FechaPago dentro del periodo del lote", score_impact=1)
        return RuleResult(
            False, "FechaPago (%s) fuera del periodo del lote (%s..%s)" % (fp, ds, de),
            details=self.evidence(valor_xml=str(fp), valor_odoo="%s..%s" % (ds, de),
                                  lote=run.name),
            score_impact=-4)


@cfdi_rule
class RuleNomLoteImporte(_NominaConLote):
    code = "NOM_052_LOTE_IMPORTE"
    name = "Nomina: importe de la poliza vs suma del lote (poliza por lote)"
    description = ("Cuando la nomina se contabiliza con UNA poliza por lote, el "
                   "importe de la poliza debe coincidir con la SUMA de netos de "
                   "todos los recibos del lote (no con un solo CFDI). Refina NOM_064. "
                   "Opt-in: encender solo en clientes con poliza por lote.")
    default_severity = SEV_HIGH
    sat_reference = _SAT_REF

    def applies(self, ctx) -> bool:
        return super().applies(ctx) and bool(
            getattr(ctx.cfdi_record, "related_move_id", None))

    def execute(self, ctx):
        run = find_run(find_payslip(ctx, find_employee(ctx)))
        move = ctx.cfdi_record.related_move_id
        slips = run.slip_ids if "slip_ids" in run._fields else None
        if not slips:
            return RuleResult(True, "El lote no expone sus recibos para sumar", score_impact=0)
        suma = Decimal("0")
        comparable = False
        for s in slips:
            net = payslip_net(s)
            if net is not None:
                suma += net
                comparable = True
        if not comparable:
            return RuleResult(True, "Recibos del lote sin neto comparable", score_impact=0)
        tol = self.tolerance(ctx, "0.01")
        move_total = Decimal(str(move.amount_total or 0))
        diff = abs(suma - move_total)
        if diff <= tol:
            return RuleResult(True, "Importe de la poliza coincide con la suma del lote",
                              score_impact=2)
        return RuleResult(
            False, "Suma del lote (%s) distinta al importe de la poliza (%s)"
            % (suma, move_total),
            details=self.evidence(valor_xml=str(suma), valor_odoo=str(move_total),
                                  diferencia=str(diff), poliza=move.name, lote=run.name),
            score_impact=-12)
