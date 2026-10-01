# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_SAT, SEVERITY_ERROR


@cfdi_rule
class RuleSelloPresente(BaseCfdiRule):
    """Verifica presencia y formato de sello CFD/SAT.

    La validacion criptografica completa (verificacion del sello con la
    llave publica del certificado) se delega al PAC durante el timbrado;
    a nivel de receptor basta con confirmar presencia y longitud razonable.
    """
    code = "SAT_020_SELLO_PRESENTE"
    name = "Sello CFD/SAT presente"
    category = CATEGORY_SAT
    default_severity = SEVERITY_ERROR
    sat_reference = "Anexo 20 RMF - Timbre Fiscal Digital"

    MIN_LEN = 200

    def execute(self, ctx):
        cfdi = ctx.cfdi
        missing = []
        if not cfdi.sello_cfd or len(cfdi.sello_cfd) < self.MIN_LEN:
            missing.append("Sello")
        if not cfdi.sello_sat or len(cfdi.sello_sat) < self.MIN_LEN:
            missing.append("SelloSAT")
        if not cfdi.no_certificado:
            missing.append("NoCertificado")
        if not cfdi.no_certificado_sat:
            missing.append("NoCertificadoSAT")
        if missing:
            return RuleResult(
                False, f"Faltan o son invalidos: {', '.join(missing)}",
                details={"missing": missing}, score_impact=-40,
            )
        return RuleResult(True, score_impact=5)
