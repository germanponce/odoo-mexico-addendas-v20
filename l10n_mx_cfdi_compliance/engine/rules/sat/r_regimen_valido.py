# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_SAT, SEVERITY_WARNING

# Catalogo c_RegimenFiscal SAT (subset comun). Lista no exhaustiva pero
# cubre los regimenes vigentes mas frecuentes; ampliable via parametros.
REGIMENES_VALIDOS = {
    "601",  # General de Ley Personas Morales
    "603",  # Personas Morales con Fines no Lucrativos
    "605",  # Sueldos y Salarios e Ingresos Asimilados a Salarios
    "606",  # Arrendamiento
    "607",  # Regimen de Enajenacion o Adquisicion de Bienes
    "608",  # Demas ingresos
    "610",  # Residentes en el Extranjero sin Establecimiento Permanente
    "611",  # Ingresos por Dividendos
    "612",  # Personas Fisicas con Actividades Empresariales y Profesionales
    "614",  # Ingresos por intereses
    "615",  # Regimen de los ingresos por obtencion de premios
    "616",  # Sin obligaciones fiscales
    "620",  # Sociedades Cooperativas de Produccion
    "621",  # Incorporacion Fiscal
    "622",  # Actividades Agricolas, Ganaderas, Silvicolas y Pesqueras
    "623",  # Opcional para Grupos de Sociedades
    "624",  # Coordinados
    "625",  # Regimen Plataformas Tecnologicas
    "626",  # Regimen Simplificado de Confianza (RESICO)
}


@cfdi_rule
class RuleRegimenValido(BaseCfdiRule):
    code = "SAT_060_REGIMEN_VALIDO"
    name = "Regimen fiscal valido (catalogo SAT)"
    category = "sat"
    default_severity = SEVERITY_WARNING
    sat_reference = "Catalogo c_RegimenFiscal Anexo 20"

    def execute(self, ctx):
        bad = []
        if ctx.cfdi.regimen_fiscal_emisor and \
                ctx.cfdi.regimen_fiscal_emisor not in REGIMENES_VALIDOS:
            bad.append(f"emisor={ctx.cfdi.regimen_fiscal_emisor}")
        if ctx.cfdi.regimen_fiscal_receptor and \
                ctx.cfdi.regimen_fiscal_receptor not in REGIMENES_VALIDOS:
            bad.append(f"receptor={ctx.cfdi.regimen_fiscal_receptor}")
        if bad:
            return RuleResult(
                False, f"Regimen fiscal fuera de catalogo: {', '.join(bad)}",
                details={"invalid": bad}, score_impact=-15,
            )
        return RuleResult(True, score_impact=2)
