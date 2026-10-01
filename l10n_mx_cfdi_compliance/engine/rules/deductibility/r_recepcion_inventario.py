# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_DEDUCTIBILITY, SEVERITY_WARNING


@cfdi_rule
class RuleRecepcionInventario(BaseCfdiRule):
    code = "DED_050_RECEPCION_INVENTARIO"
    name = "Recepcion de inventario asociada (3-way match)"
    description = ("Si el CFDI corresponde a productos almacenables, debe existir "
                   "stock.picking de recepcion confirmado.")
    category = CATEGORY_DEDUCTIBILITY
    default_severity = SEVERITY_WARNING

    def applies(self, ctx):
        return bool(ctx.cfdi_record.related_purchase_id)

    def execute(self, ctx):
        po = ctx.cfdi_record.related_purchase_id
        pickings = po.picking_ids.filtered(
            lambda p: p.state == "done" and p.picking_type_id.code == "incoming"
        )
        if not pickings:
            return RuleResult(
                False,
                f"OC {po.name} sin recepcion confirmada",
                details={"purchase_id": po.id},
                score_impact=-15,
            )
        return RuleResult(True, score_impact=3)
