# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from odoo import api, fields, models, _
from odoo.exceptions import UserError


BLOCKING_STATES = ("blocked", "authorization_required", "rejected", "error")


class AccountMove(models.Model):
    _inherit = "account.move"

    cfdi_document_id = fields.Many2one(
        "l10n_mx.cfdi.document", copy=False, index=True,
    )
    cfdi_compliance_state = fields.Selection(
        related="cfdi_document_id.compliance_state",
        store=True, readonly=True,
    )
    cfdi_compliance_score = fields.Integer(
        related="cfdi_document_id.compliance_score",
        store=True, readonly=True,
    )
    compliance_profile_id = fields.Many2one(
        "l10n_mx.compliance.profile",
        help="Sobreescribe el perfil de compliance para esta factura.",
    )

    def action_post(self):
        for move in self.filtered(lambda m: m.move_type in ("in_invoice", "in_refund")):
            move._check_cfdi_compliance_before_post()
        return super().action_post()

    def _check_cfdi_compliance_before_post(self):
        self.ensure_one()
        # Find candidate CFDI document either via FK or via attachment
        doc = self.cfdi_document_id
        if not doc:
            # v.68: is_cfdi_xml es store=False (no se puede usar como filtro
            # SQL). Filtramos por name/mimetype directamente en SQL y validamos
            # contenido en Python.
            attachments = self.env["ir.attachment"].sudo().search([
                ("res_model", "=", "account.move"),
                ("res_id", "=", self.id),
                "|", ("name", "=ilike", "%.xml"), ("mimetype", "ilike", "%xml%"),
            ])
            attachments = attachments.filtered(lambda a: a._is_cfdi_xml_safe())
            doc = attachments.mapped("cfdi_document_id")[:1]
            if doc:
                self.cfdi_document_id = doc
        if not doc:
            # No CFDI attached; let it pass (may be a manual draft)
            return
        if doc.compliance_state in BLOCKING_STATES:
            raise UserError(_(
                "No se puede contabilizar: el CFDI %s tiene estado de compliance '%s'. "
                "Score: %s. Resuelva el bloqueo o solicite autorizacion."
            ) % (doc.display_name, dict(doc._fields["compliance_state"].selection)
                 .get(doc.compliance_state), doc.compliance_score))
