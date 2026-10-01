# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_SAT, SEVERITY_WARNING


@cfdi_rule
class RuleXmlHashDuplicado(BaseCfdiRule):
    code = "SAT_011_HASH_DUPLICADO"
    name = "XML byte-identico ya cargado"
    description = "Detecta carga del MISMO archivo XML mas de una vez."
    category = CATEGORY_SAT
    default_severity = SEVERITY_WARNING

    def execute(self, ctx):
        Doc = ctx.env["l10n_mx.cfdi.document"].sudo()
        existing = Doc.search_count([
            ("xml_hash", "=", ctx.cfdi.xml_hash),
            ("company_id", "=", ctx.company.id),
            ("id", "!=", ctx.cfdi_record.id),
        ])
        if existing:
            return RuleResult(
                False,
                f"Archivo XML ya cargado anteriormente ({existing} vez/veces)",
                details={"existing_count": existing},
                score_impact=-15,
            )
        return RuleResult(True, score_impact=2)
