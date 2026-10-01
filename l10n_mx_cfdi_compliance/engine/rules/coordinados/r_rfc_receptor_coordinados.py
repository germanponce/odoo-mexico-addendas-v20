# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from ...base_rule import (
    BaseCfdiRule, RuleResult, cfdi_rule,
    CATEGORY_COORDINADOS, SEVERITY_ERROR,
)
from ...resolvers.receptor_resolver import CfdiReceptorResolver


@cfdi_rule
class RuleRfcReceptorCoordinados(BaseCfdiRule):
    """Permite que el RFC receptor coincida con la compania actual O con
    una de las coordinadas vigentes registradas en
    ``l10n_mx.cfdi.coordinado.relation``.
    """
    code = "COORD_001_RFC_RECEPTOR"
    name = "RFC receptor (compania o coordinada vigente)"
    description = ("Acepta CFDIs cuyo RFC receptor sea la compania actual o una "
                   "coordinada/AGAPE vigente bajo regimen 624 LISR.")
    category = CATEGORY_COORDINADOS
    default_severity = SEVERITY_ERROR
    sat_reference = "Art. 72-73 LISR (Coordinados)"
    short_circuit_on_fail = False

    def applies(self, ctx):
        # No aplica a NOMINA: el receptor es el empleado, nunca la compania ni una
        # coordinada -> generaria un falso "RFC receptor no coincide".
        if ctx.cfdi_record.tipo_comprobante == "N":
            return False
        # Solo aplica si la compania OPERA en regimen de coordinados, es decir tiene
        # al menos una relacion controladora<->coordinada vigente configurada. Para
        # una empresa NORMAL (sin coordinadas) esta regla no tiene sentido y solo
        # generaria ruido (receptor != compania en cada factura de cliente).
        return bool(ctx.env["l10n_mx.cfdi.coordinado.relation"].sudo().search_count([
            ("controladora_company_id", "=", ctx.company.id),
            ("active", "=", True),
        ]))

    def execute(self, ctx):
        resolver = CfdiReceptorResolver()
        r = resolver.resolve(
            ctx.env, ctx.company,
            ctx.cfdi.rfc_receptor, ctx.cfdi.fecha,
        )
        ctx.receptor_resolution = r
        if not r["valid"]:
            return RuleResult(
                False,
                f"RFC receptor {ctx.cfdi.rfc_receptor} no coincide con compania "
                f"{ctx.company.vat or '(sin VAT)'} ni con coordinadas vigentes",
                details=r, score_impact=-40,
            )
        # Stamp marker fields on the document for downstream UI/reporting.
        ctx.cfdi_record.write({
            "is_coordinado_cross": r["mode"] == "coordinado",
            "receptor_company_id": r["receptor_company"].id if r["receptor_company"] else False,
            "coordinado_relation_id": r["relation"].id if r["relation"] else False,
        })
        msg = ("Receptor directo" if r["mode"] == "direct"
               else f"Receptor coordinado: {r['receptor_company'].display_name}")
        return RuleResult(True, msg, details={"mode": r["mode"]}, score_impact=5)
