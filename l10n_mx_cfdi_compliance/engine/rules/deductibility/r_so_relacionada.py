# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_DEDUCTIBILITY, SEVERITY_WARNING


@cfdi_rule
class RuleSoRelacionada(BaseCfdiRule):
    code = "DED_041_SO_RELACIONADA"
    name = "CFDI cliente vinculado a Orden de Venta"
    description = ("Si la compania exige Orden de Venta, la factura de cliente "
                   "(emitida, Ingreso) debe vincularse a una sale.order. "
                   "Analogo a DED_040 (Orden de Compra) del lado de ventas.")
    category = CATEGORY_DEDUCTIBILITY
    default_severity = SEVERITY_WARNING

    def applies(self, ctx):
        # Solo factura de CLIENTE: emitido + Ingreso.
        rec = ctx.cfdi_record
        return rec.tipo_comprobante == "I" and rec.direccion == "emitido"

    def execute(self, ctx):
        move = ctx.cfdi_record.related_move_id
        # La factura de cliente generada desde una Orden de Venta lleva
        # invoice_origin = nombre de la sale.order.
        if move and move.invoice_origin:
            return RuleResult(True, "Factura con Orden de Venta (origen)",
                              score_impact=1)
        return RuleResult(
            False, "Factura de cliente sin Orden de Venta relacionada",
            score_impact=-10,
        )
