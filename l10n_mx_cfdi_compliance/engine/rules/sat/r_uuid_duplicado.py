# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_SAT, SEVERITY_ERROR


@cfdi_rule
class RuleUuidDuplicado(BaseCfdiRule):
    code = "SAT_010_UUID_DUPLICADO"
    name = "UUID duplicado en compania"
    description = "Detecta si el UUID ya fue registrado en otra factura de la compania."
    category = CATEGORY_SAT
    default_severity = SEVERITY_ERROR
    sat_reference = "Art. 29-A CFF fracc. III"

    def execute(self, ctx):
        Doc = ctx.env["l10n_mx.cfdi.document"].sudo()
        existing = Doc.search_count([
            ("uuid", "=", ctx.cfdi.uuid),
            ("company_id", "=", ctx.company.id),
            ("id", "!=", ctx.cfdi_record.id),
        ])
        if existing:
            return RuleResult(
                False,
                f"UUID {ctx.cfdi.uuid} ya registrado en {existing} documento(s) previo(s)",
                details={"existing_count": existing},
                score_impact=-50,
            )
        return RuleResult(True, score_impact=5)
