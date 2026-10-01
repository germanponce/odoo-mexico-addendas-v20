# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_SAT, SEVERITY_ERROR
from ...sat_clients import lista_69b_client


@cfdi_rule
class RuleLista69B(BaseCfdiRule):
    code = "SAT_040_LISTA_69B"
    name = "Emisor en lista 69-B SAT (EFOS)"
    description = "Verifica que el RFC emisor no este publicado como EFOS en la lista 69-B."
    category = CATEGORY_SAT
    requires_internet = True
    default_severity = SEVERITY_ERROR
    sat_reference = "Art. 69-B CFF"

    def execute(self, ctx):
        rfc = ctx.cfdi.rfc_emisor
        rec = lista_69b_client.get_69b_record(ctx.env, rfc)
        if rec is None or not rec:
            # Not in our local DB: cannot conclude.
            return RuleResult(
                True,
                "RFC no localizado en lista 69-B local "
                "(verifique sincronizacion del modulo l10n_mx_xml_massive_download)",
                details={"rfc": rfc, "verified": False},
                score_impact=0,
            )
        if not rec.activo or rec.situacion == "desvirtuado":
            return RuleResult(
                True, "Emisor en historial 69-B pero DESVIRTUADO por SAT",
                details={
                    "rfc": rfc, "verified": True,
                    "situacion": rec.situacion,
                    "fecha_publicacion": str(rec.fecha_publicacion or ""),
                },
                score_impact=5,
            )
        sev_msg = {
            "presuncion": "PRESUNTO EFOS",
            "definitivo": "DEFINITIVO EFOS",
        }.get(rec.situacion, rec.situacion or "EFOS")
        return RuleResult(
            False,
            f"RFC emisor {rfc} aparece en LISTA 69-B SAT ({sev_msg})",
            details={
                "rfc": rfc, "verified": True,
                "situacion": rec.situacion,
                "razon_social": rec.razon_social,
                "fecha_publicacion": str(rec.fecha_publicacion or ""),
                "numero_publicacion": rec.numero_publicacion,
                "supuesto": rec.supuesto,
            },
            score_impact=-100,
        )
