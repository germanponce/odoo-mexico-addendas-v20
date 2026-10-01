# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from ...base_rule import (
    BaseCfdiRule, RuleResult, cfdi_rule,
    CATEGORY_SAT, SEVERITY_ERROR,
)


@cfdi_rule
class RuleXmlValido(BaseCfdiRule):
    code = "SAT_001_XML_VALIDO"
    name = "XML CFDI bien formado"
    description = "Verifica que el XML pudo ser parseado como CFDI 4.0 con UUID."
    category = CATEGORY_SAT
    default_severity = SEVERITY_ERROR
    sat_reference = "Anexo 20 RMF"
    short_circuit_on_fail = True

    def execute(self, ctx):
        cfdi = ctx.cfdi
        if not cfdi or not cfdi.uuid:
            return RuleResult(False, "CFDI sin UUID o malformado", score_impact=-100)
        if cfdi.version != "4.0":
            return RuleResult(
                False, f"Version CFDI no soportada: {cfdi.version} (esperada 4.0)",
                score_impact=-50,
            )
        return RuleResult(True, score_impact=10)
