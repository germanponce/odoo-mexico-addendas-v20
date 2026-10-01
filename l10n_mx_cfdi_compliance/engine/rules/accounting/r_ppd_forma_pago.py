# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_ACCOUNTING, SEVERITY_ERROR


@cfdi_rule
class RulePpdFormaPago(BaseCfdiRule):
    code = "ACC_011_PPD_FORMA_PAGO"
    name = "PPD debe usar Forma de Pago 99"
    description = "Los CFDIs con MetodoPago=PPD deben usar FormaPago=99 (Por definir)."
    category = CATEGORY_ACCOUNTING
    default_severity = SEVERITY_ERROR
    sat_reference = "Guia llenado CFDI - Apendice 4"

    def applies(self, ctx):
        return ctx.cfdi.tipo_comprobante in ("I", "E") and ctx.cfdi.metodo_pago == "PPD"

    def execute(self, ctx):
        if ctx.cfdi.forma_pago != "99":
            return RuleResult(
                False,
                f"PPD requiere FormaPago=99; se recibio {ctx.cfdi.forma_pago!r}",
                score_impact=-25,
            )
        return RuleResult(True, score_impact=2)
