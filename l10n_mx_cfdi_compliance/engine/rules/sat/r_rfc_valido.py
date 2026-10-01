# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
import re
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_SAT, SEVERITY_ERROR

# RFC SAT regex (PM 12 chars / PF 13 chars; alfanumerico)
RFC_RE = re.compile(r"^[A-ZÑ&]{3,4}[0-9]{2}(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])[A-Z0-9]{2}[0-9A]$")


@cfdi_rule
class RuleRfcValido(BaseCfdiRule):
    code = "SAT_050_RFC_VALIDO"
    name = "Formato de RFC valido (emisor y receptor)"
    category = CATEGORY_SAT
    default_severity = SEVERITY_ERROR
    sat_reference = "Art. 27 CFF"

    def execute(self, ctx):
        bad = []
        for label, rfc in (
            ("emisor", ctx.cfdi.rfc_emisor),
            ("receptor", ctx.cfdi.rfc_receptor),
        ):
            if not rfc or not RFC_RE.match(rfc):
                bad.append(f"{label}={rfc!r}")
        if bad:
            return RuleResult(
                False, f"RFC con formato invalido: {', '.join(bad)}",
                details={"invalid": bad}, score_impact=-30,
            )
        return RuleResult(True, score_impact=2)
