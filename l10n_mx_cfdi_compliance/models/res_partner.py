# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    compliance_profile_id = fields.Many2one(
        "l10n_mx.compliance.profile",
        string="Perfil CFDI Compliance (override)",
        company_dependent=True,
        help="Si se define, sustituye al perfil por defecto de la compania "
             "para CFDIs de este proveedor.",
    )
    cfdi_compliance_score_avg = fields.Float(
        compute="_compute_compliance_avg", store=False,
        string="Score CFDI promedio",
    )
    cfdi_blocked_count = fields.Integer(
        compute="_compute_compliance_avg", store=False,
        string="CFDIs bloqueados",
    )

    def _compute_compliance_avg(self):
        Doc = self.env["l10n_mx.cfdi.document"].sudo()
        for p in self:
            docs = Doc.search([("rfc_emisor", "=", (p.vat or "").upper())])
            p.cfdi_compliance_score_avg = (
                sum(docs.mapped("compliance_score")) / len(docs)
            ) if docs else 0
            p.cfdi_blocked_count = len(docs.filtered(
                lambda d: d.compliance_state in ("blocked", "rejected")
            ))
