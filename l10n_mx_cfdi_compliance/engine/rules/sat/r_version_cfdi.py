# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_SAT, SEVERITY_ERROR


@cfdi_rule
class RuleVersionCfdi(BaseCfdiRule):
    code = "SAT_002_VERSION_CFDI"
    name = "Version CFDI 4.0"
    category = CATEGORY_SAT
    default_severity = SEVERITY_ERROR
    sat_reference = "Anexo 20 RMF 2022 (vigente desde 2023)"

    def execute(self, ctx):
        if ctx.cfdi.version != "4.0":
            return RuleResult(
                False, f"Solo se acepta CFDI 4.0; recibido {ctx.cfdi.version}",
                score_impact=-50,
            )
        return RuleResult(True, score_impact=2)
