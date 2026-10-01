# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    cfdi_document_ids = fields.One2many(
        "l10n_mx.cfdi.document", "related_purchase_id",
        string="CFDIs Relacionados",
    )
    cfdi_count = fields.Integer(compute="_compute_cfdi_count")

    def _compute_cfdi_count(self):
        for po in self:
            po.cfdi_count = len(po.cfdi_document_ids)

    def action_view_cfdi_documents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "CFDIs",
            "res_model": "l10n_mx.cfdi.document",
            "view_mode": "list,form",
            "domain": [("related_purchase_id", "=", self.id)],
        }
