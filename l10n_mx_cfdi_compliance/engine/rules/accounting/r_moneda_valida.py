# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_ACCOUNTING, SEVERITY_WARNING

# c_Moneda SAT (subset comun)
MONEDAS_VALIDAS = {
    "MXN", "USD", "EUR", "CAD", "GBP", "JPY", "CNY", "CHF", "AUD", "BRL",
    "ARS", "CLP", "COP", "PEN", "UYU", "VES", "XXX",
}


@cfdi_rule
class RuleMonedaValida(BaseCfdiRule):
    code = "ACC_040_MONEDA_VALIDA"
    name = "Moneda en catalogo SAT"
    category = CATEGORY_ACCOUNTING
    default_severity = SEVERITY_WARNING
    sat_reference = "Catalogo c_Moneda"

    def execute(self, ctx):
        if ctx.cfdi.moneda and ctx.cfdi.moneda not in MONEDAS_VALIDAS:
            return RuleResult(
                False, f"Moneda fuera de catalogo: {ctx.cfdi.moneda}",
                score_impact=-10,
            )
        return RuleResult(True, score_impact=1)
