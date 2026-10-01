# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_DEDUCTIBILITY, SEVERITY_WARNING


@cfdi_rule
class RuleOcRelacionada(BaseCfdiRule):
    code = "DED_040_OC_RELACIONADA"
    name = "CFDI vinculado a Orden de Compra"
    description = ("Si la compania exige OC, el CFDI debe vincularse a una "
                   "purchase.order del proveedor.")
    category = CATEGORY_DEDUCTIBILITY
    default_severity = SEVERITY_WARNING

    def applies(self, ctx):
        # Solo factura de PROVEEDOR: recibido + Ingreso. Una factura de cliente
        # (emitido) no tiene Orden de Compra -> ver DED_041 (Orden de Venta).
        rec = ctx.cfdi_record
        return rec.tipo_comprobante == "I" and rec.direccion == "recibido"

    def execute(self, ctx):
        rec = ctx.cfdi_record
        if rec.related_purchase_id:
            return RuleResult(True, score_impact=2)
        # Try auto-link by partner + amount
        Move = ctx.env["account.move"]
        if rec.related_move_id and rec.related_move_id.invoice_origin:
            return RuleResult(True, "Move tiene invoice_origin", score_impact=1)
        return RuleResult(
            False, "CFDI sin Orden de Compra relacionada",
            score_impact=-10,
        )
