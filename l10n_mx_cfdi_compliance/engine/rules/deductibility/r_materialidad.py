# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from decimal import Decimal
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_DEDUCTIBILITY, SEVERITY_AUTHORIZATION


@cfdi_rule
class RuleMaterialidad(BaseCfdiRule):
    """Cuando el monto supera el umbral configurado, exige evidencia
    de materialidad: contrato, OC, recepcion u otro soporte."""
    code = "DED_030_MATERIALIDAD"
    name = "Materialidad - evidencia de operacion real"
    description = ("Para CFDIs por encima del umbral, requiere autorizacion si "
                   "no existen documentos de respaldo (contrato, OC, recepcion).")
    category = CATEGORY_DEDUCTIBILITY
    default_severity = SEVERITY_AUTHORIZATION
    sat_reference = "Criterio SAT - Materialidad de operaciones"

    DEFAULT_THRESHOLD = Decimal("100000")

    def applies(self, ctx):
        # Materialidad aplica a DEDUCCIONES (gastos): solo recibidos. Un CFDI
        # emitido (ingreso del contribuyente) no se deduce -> no requiere
        # OC/recepcion/anexos de respaldo de compra.
        return ctx.cfdi_record.direccion == "recibido"

    def execute(self, ctx):
        params = next(
            (c.params for c in ctx.profile.rule_config_ids
             if c.rule_id.code == self.code), None,
        ) or {}
        threshold = Decimal(str(params.get("threshold_mxn", self.DEFAULT_THRESHOLD)))
        if ctx.cfdi.total < threshold:
            return RuleResult(True, "Por debajo de umbral de materialidad",
                              score_impact=0)
        # Look for related move or PO
        move = ctx.cfdi_record.related_move_id
        po = ctx.cfdi_record.related_purchase_id
        has_po = bool(po)
        has_attachments = False
        if move:
            has_attachments = bool(ctx.env["ir.attachment"].search_count([
                ("res_model", "=", "account.move"),
                ("res_id", "=", move.id),
                ("id", "!=", ctx.cfdi_record.attachment_id.id),
            ]))
        if has_po or has_attachments:
            return RuleResult(True, "Materialidad sustentada", score_impact=5)
        return RuleResult(
            False,
            f"Monto >= {threshold} MXN sin OC ni anexos de respaldo: requiere autorizacion",
            details={"threshold": str(threshold), "total": str(ctx.cfdi.total)},
            score_impact=-25,
        )
