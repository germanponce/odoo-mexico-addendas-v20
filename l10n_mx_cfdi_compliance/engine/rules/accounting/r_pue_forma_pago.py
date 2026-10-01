# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_ACCOUNTING, SEVERITY_ERROR


@cfdi_rule
class RulePueFormaPago(BaseCfdiRule):
    code = "ACC_010_PUE_FORMA_PAGO"
    name = "PUE no debe usar Forma de Pago 99"
    description = ("CFDIs con MetodoPago=PUE deben tener una FormaPago especifica "
                   "(no '99 - Por definir').")
    category = CATEGORY_ACCOUNTING
    default_severity = SEVERITY_ERROR
    sat_reference = "Guia llenado CFDI - Apendice 4"

    def applies(self, ctx):
        return ctx.cfdi.tipo_comprobante in ("I", "E") and ctx.cfdi.metodo_pago == "PUE"

    def execute(self, ctx):
        if ctx.cfdi.forma_pago == "99":
            return RuleResult(
                False, "PUE no admite FormaPago=99 (Por definir)",
                score_impact=-30,
            )
        if not ctx.cfdi.forma_pago:
            return RuleResult(False, "PUE sin FormaPago", score_impact=-25)
        return RuleResult(True, score_impact=2)
