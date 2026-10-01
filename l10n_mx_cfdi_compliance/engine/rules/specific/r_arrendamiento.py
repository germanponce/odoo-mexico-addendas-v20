# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_SPECIFIC, SEVERITY_WARNING

# ClaveProdServ - servicios de arrendamiento/alquiler de bienes inmuebles (UNSPSC):
#   801315xx - Servicios de alquiler o arrendamiento de propiedades o edificaciones
#   801316xx - Alquiler de propiedades / espacios de oficina, comercial, industrial, etc.
# Excluye 80141xxx (marketing/distribution, rebate management, eventos) que NO es
# arrendamiento aunque parezca por el prefijo 8014.
ARRENDAMIENTO_CLAVES = ("801315", "801316")


@cfdi_rule
class RuleArrendamiento(BaseCfdiRule):
    code = "SPEC_020_ARRENDAMIENTO"
    name = "Arrendamiento: retenciones de IVA / ISR"
    description = ("CFDIs de arrendamiento de personas fisicas deben incluir "
                   "retencion de ISR (10%) y eventualmente IVA (10.6667%).")
    category = CATEGORY_SPECIFIC
    default_severity = SEVERITY_WARNING
    sat_reference = "Art. 116 LISR"

    def applies(self, ctx):
        return any(
            (c.clave_prod_serv or "").startswith(ARRENDAMIENTO_CLAVES)
            for c in ctx.cfdi.conceptos
        )

    def execute(self, ctx):
        if not ctx.cfdi.impuestos_retenidos:
            return RuleResult(
                False,
                "Arrendamiento sin retenciones declaradas",
                score_impact=-15,
            )
        return RuleResult(True, score_impact=2)
