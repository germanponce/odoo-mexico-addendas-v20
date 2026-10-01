# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_DEDUCTIBILITY, SEVERITY_WARNING

OBJETO_IMP_VALIDOS = {"01", "02", "03", "04"}
# 01 = No objeto del impuesto
# 02 = Si objeto del impuesto
# 03 = Si objeto del impuesto y no obligado al desglose
# 04 = Si objeto del impuesto y no causa impuesto


@cfdi_rule
class RuleObjetoImpuesto(BaseCfdiRule):
    code = "DED_020_OBJETO_IMPUESTO"
    name = "ObjetoImp valido en cada concepto"
    category = CATEGORY_DEDUCTIBILITY
    default_severity = SEVERITY_WARNING
    sat_reference = "Anexo 20 - ObjetoImp"

    def execute(self, ctx):
        bad = []
        for i, c in enumerate(ctx.cfdi.conceptos):
            if c.objeto_imp not in OBJETO_IMP_VALIDOS:
                bad.append({"idx": i, "objeto_imp": c.objeto_imp,
                            "descripcion": c.descripcion[:60]})
        if bad:
            return RuleResult(
                False, f"{len(bad)} concepto(s) con ObjetoImp invalido",
                details={"conceptos": bad}, score_impact=-15,
            )
        return RuleResult(True, score_impact=2)
