# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from decimal import Decimal
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_ACCOUNTING, SEVERITY_WARNING


@cfdi_rule
class RuleTipoCambio(BaseCfdiRule):
    code = "ACC_030_TIPO_CAMBIO"
    name = "Tipo de cambio coherente con moneda"
    description = ("Si la moneda es MXN el tipo de cambio debe ser 1; "
                   "si es extranjera, debe ser distinto de 1 y razonable.")
    category = CATEGORY_ACCOUNTING
    default_severity = SEVERITY_WARNING
    sat_reference = "Art. 20 CFF"

    def execute(self, ctx):
        cfdi = ctx.cfdi
        if cfdi.moneda == "MXN":
            if cfdi.tipo_cambio not in (Decimal("1"), Decimal("0")):
                return RuleResult(
                    False, f"Moneda MXN debe llevar TipoCambio=1, "
                    f"se recibio {cfdi.tipo_cambio}",
                    score_impact=-10,
                )
        else:
            if cfdi.tipo_cambio <= Decimal("1"):
                return RuleResult(
                    False, f"Moneda {cfdi.moneda} con TipoCambio sospechoso "
                    f"({cfdi.tipo_cambio})", score_impact=-15,
                )
        return RuleResult(True, score_impact=2)
