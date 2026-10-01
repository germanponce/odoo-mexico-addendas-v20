# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from decimal import Decimal
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_ACCOUNTING, SEVERITY_WARNING


@cfdi_rule
class RuleIvaCalculo(BaseCfdiRule):
    code = "ACC_020_IVA_CALCULO"
    name = "Coherencia de impuestos trasladados (root)"
    description = (
        "Verifica que TotalImpuestosTrasladados declarado en el root del CFDI "
        "coincida con la suma de Importes de los nodos cfdi:Traslado del root. "
        "Incluye IVA + IEPS + cualquier otro impuesto trasladado."
    )
    category = CATEGORY_ACCOUNTING
    default_severity = SEVERITY_WARNING
    sat_reference = "Anexo 20 CFDI 4.0 - cfdi:Impuestos"

    TOLERANCE = Decimal("0.50")  # MXN tolerance for rounding

    def execute(self, ctx):
        cfdi = ctx.cfdi
        declared = cfdi.total_impuestos_trasladados
        if not declared and not cfdi.impuestos_trasladados:
            return RuleResult(True, "Sin impuestos trasladados", score_impact=0)
        sum_root = sum(
            (i.importe for i in cfdi.impuestos_trasladados),
            Decimal("0"),
        )
        if abs(declared - sum_root) > self.TOLERANCE:
            return RuleResult(
                False,
                f"TotalImpuestosTrasladados declarado={declared} "
                f"vs suma de cfdi:Traslado={sum_root}",
                details={
                    "declarado": str(declared),
                    "calculado": str(sum_root),
                },
                score_impact=-15,
            )
        return RuleResult(True, score_impact=2)
