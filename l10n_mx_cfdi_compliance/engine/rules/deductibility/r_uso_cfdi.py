# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_DEDUCTIBILITY, SEVERITY_WARNING

# c_UsoCFDI vigentes (CFDI 4.0)
USOS_CFDI_VIGENTES = {
    "G01", "G02", "G03",
    "I01", "I02", "I03", "I04", "I05", "I06", "I07", "I08",
    "D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08", "D09", "D10",
    "S01", "CP01", "CN01",
}

# Usos NO deducibles -> warning fuerte para empresas
USOS_NO_DEDUCIBLES = {"S01", "CP01", "CN01"}


@cfdi_rule
class RuleUsoCfdi(BaseCfdiRule):
    code = "DED_010_USO_CFDI"
    name = "Uso CFDI valido y deducible"
    category = CATEGORY_DEDUCTIBILITY
    default_severity = SEVERITY_WARNING
    sat_reference = "Catalogo c_UsoCFDI"

    def applies(self, ctx):
        # La DEDUCIBILIDAD del Uso CFDI aplica a GASTOS (recibidos): es el uso que
        # determina si TU compania puede deducir el comprobante recibido. En CFDIs
        # EMITIDOS no es una observacion de deducibilidad propia (el uso lo define el
        # cliente). En particular un recibo de NOMINA (emitido, tipo N) lleva uso
        # CN01 por catalogo -> no es un hallazgo de "no deducible". Solo recibidos.
        return ctx.cfdi_record.direccion == "recibido"

    def execute(self, ctx):
        uso = ctx.cfdi.uso_cfdi
        if not uso:
            return RuleResult(False, "Sin Uso CFDI", score_impact=-10)
        if uso not in USOS_CFDI_VIGENTES:
            return RuleResult(
                False, f"Uso CFDI fuera de catalogo vigente: {uso}",
                score_impact=-15,
            )
        if uso in USOS_NO_DEDUCIBLES:
            return RuleResult(
                False, f"Uso CFDI {uso} es NO deducible (informativo/sin efectos fiscales)",
                score_impact=-20,
            )
        return RuleResult(True, score_impact=2)
