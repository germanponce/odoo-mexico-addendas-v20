# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_SPECIFIC, SEVERITY_WARNING

# ClaveProdServ - servicios de arrendamiento/alquiler de bienes inmuebles (UNSPSC):
#   801315xx - Servicios de alquiler o arrendamiento de propiedades o edificaciones
#   801316xx - Alquiler de propiedades / espacios de oficina, comercial, industrial, etc.
# La cuenta predial municipal solo es obligatoria para arrendamiento de inmuebles,
# no para servicios de marketing/promocion (familia 8014xxxx) ni venta de inmuebles (801318xx).
ARRENDAMIENTO_CLAVES = ("801315", "801316")


@cfdi_rule
class RuleCuentaPredial(BaseCfdiRule):
    code = "SPEC_021_CUENTA_PREDIAL"
    name = "Arrendamiento: numero de cuenta predial del inmueble"
    description = (
        "CFDIs de arrendamiento de inmuebles deben incluir el nodo "
        "<cfdi:CuentaPredial Numero='...'/> dentro de cada concepto, con el "
        "numero de cuenta predial municipal del inmueble arrendado."
    )
    category = CATEGORY_SPECIFIC
    default_severity = SEVERITY_WARNING
    sat_reference = "Anexo 20 / Guia de llenado CFDI 4.0 - nodo CuentaPredial"

    def applies(self, ctx):
        return any(
            (c.clave_prod_serv or "").startswith(ARRENDAMIENTO_CLAVES)
            for c in ctx.cfdi.conceptos
        )

    def execute(self, ctx):
        sin_predial = [
            c for c in ctx.cfdi.conceptos
            if (c.clave_prod_serv or "").startswith(ARRENDAMIENTO_CLAVES)
            and not (c.cuenta_predial or "").strip()
        ]
        if sin_predial:
            return RuleResult(
                False,
                f"{len(sin_predial)} concepto(s) de arrendamiento sin numero de cuenta predial",
                details={
                    "conceptos_sin_predial": [
                        {"clave": c.clave_prod_serv, "descripcion": c.descripcion}
                        for c in sin_predial
                    ]
                },
                score_impact=-10,
            )
        return RuleResult(True, score_impact=2)
