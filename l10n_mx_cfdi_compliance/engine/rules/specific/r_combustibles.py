# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_SPECIFIC, SEVERITY_WARNING

# ClaveProdServ del SAT relacionadas con combustibles (Cap. 15-10 c_ClaveProdServ)
COMBUSTIBLE_CLAVES_PREFIJO = ("15101",)  # 1510150X gasolinas/diesel/etc.
FORMAS_PAGO_VALIDAS_COMBUSTIBLE = {"03", "04", "05", "28"}
# 03 Transferencia, 04 Tarjeta de credito, 05 Monedero electronico, 28 Tarjeta debito
# (NO admite efectivo si se quiere deducir gasolina)


@cfdi_rule
class RuleCombustibles(BaseCfdiRule):
    code = "SPEC_010_COMBUSTIBLES"
    name = "Combustibles: forma de pago restringida"
    description = ("Para deducir combustibles el pago debe ser con monedero electronico, "
                   "tarjeta o transferencia (no efectivo).")
    category = CATEGORY_SPECIFIC
    default_severity = SEVERITY_WARNING
    sat_reference = "Art. 27 fracc. III LISR"

    def applies(self, ctx):
        return any(
            (c.clave_prod_serv or "").startswith(COMBUSTIBLE_CLAVES_PREFIJO)
            for c in ctx.cfdi.conceptos
        )

    def execute(self, ctx):
        if ctx.cfdi.forma_pago not in FORMAS_PAGO_VALIDAS_COMBUSTIBLE:
            return RuleResult(
                False,
                f"Combustible con FormaPago {ctx.cfdi.forma_pago} no deducible "
                f"(requiere monedero/tarjeta/transferencia)",
                score_impact=-25,
            )
        return RuleResult(True, score_impact=3)
