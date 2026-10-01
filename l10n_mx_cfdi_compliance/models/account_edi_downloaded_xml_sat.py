# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
"""Integration with l10n_mx_xml_massive_download.

The companion module ``l10n_mx_xml_massive_download`` downloads CFDIs
from the SAT API in batches. Each downloaded XML is stored as an
``ir.attachment`` linked to ``account.edi.downloaded.xml.sat``.

Because our ``ir.attachment.create`` override fires the compliance
pipeline for *every* CFDI XML attachment, validation already happens
automatically the moment the massive download stores the XML.

What we add here:
    * Cross-link field ``cfdi_document_id`` so the user can navigate
      from the SAT downloaded record to the compliance result.
    * Override of ``action_import_invoice`` to:
        - block invoice creation when compliance is in a blocking state
          (unless an authorizer has overridden it),
        - propagate the compliance link to the freshly created
          ``account.move``.
"""
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Same set used by account.move.action_post() in this module.
_BLOCKING_STATES = ("blocked", "authorization_required", "rejected", "error")


class AccountEdiDownloadedXmlSat(models.Model):
    _inherit = "account.edi.downloaded.xml.sat"

    # v.69: store=False (computa on-demand). El campo es computed y al install
    # SIN @api.depends Odoo intenta recomputar para TODOS los registros
    # existentes — en Cosal productivo con >74K xml_sat esto NO termina en
    # ventana razonable (>10 min sin progreso). Con store=False solo se
    # computa cuando se accede al campo. El cron 87 "Compliance: evaluar
    # XMLs huerfanos" procesa los huerfanos gradualmente en background.
    cfdi_document_id = fields.Many2one(
        "l10n_mx.cfdi.document",
        string="CFDI Compliance",
        compute="_compute_cfdi_document_id",
        search="_search_cfdi_document_id",
        store=False,
        help="Resultado del Motor de Compliance Fiscal (ANFEPI) "
             "para este XML descargado del SAT. Compute on-demand para no "
             "bloquear el install del modulo en bases con mucho volumen.",
    )
    compliance_state = fields.Selection(
        related="cfdi_document_id.compliance_state",
        string="Estado Compliance",
        store=False,
    )
    compliance_score = fields.Integer(
        related="cfdi_document_id.compliance_score",
        string="Score Compliance",
        store=False,
    )

    def _compute_cfdi_document_id(self):
        """Resolve the cfdi.document either via attachment link or UUID."""
        Doc = self.env["l10n_mx.cfdi.document"].sudo()
        for rec in self:
            doc = False
            if rec.attachment_id:
                doc = Doc.search([
                    ("attachment_id", "=", rec.attachment_id.id),
                ], limit=1)
            if not doc and rec.name:
                doc = Doc.search([("uuid", "=", rec.name)], limit=1)
            rec.cfdi_document_id = doc.id if doc else False

    def _search_cfdi_document_id(self, operator, value):
        """Hace BUSCABLE el campo computed (store=False).

        Necesario para que el ORM resuelva que registros invalidar/recomputar
        cuando cambia compliance_state/compliance_score del cfdi.document
        (los campos related dependen de cfdi_document_id.*). Sin esto, Odoo emite
        UserWarning 'field ... should be searchable' al construir el registry.
        Mapea el dominio al vinculo real: attachment_id o name (uuid). El caso
        que usa el trigger de recompute es operator 'in' con ids reales.
        """
        Doc = self.env["l10n_mx.cfdi.document"]
        if isinstance(value, (list, tuple)):
            docs = Doc.browse([v for v in value if isinstance(v, int)]).exists()
        elif isinstance(value, int) and not isinstance(value, bool):
            docs = Doc.browse(value).exists()
        elif isinstance(value, str):
            sub_op = operator if operator in ("=", "!=", "like", "ilike") else "ilike"
            docs = Doc.search([("uuid", sub_op, value)])
        else:
            docs = Doc.browse([])
        att_ids = docs.mapped("attachment_id").ids
        uuids = [u for u in docs.mapped("uuid") if u]
        positive = ["|", ("attachment_id", "in", att_ids), ("name", "in", uuids)]
        if operator in ("!=", "not in"):
            return ["!", *positive]
        return positive

    def action_import_invoice(self):
        """Override: enforce compliance gating before invoice creation.

        Only applies to *recibidos* (vendor bills). Emitidos (customer
        invoices) are not subject to vendor compliance.
        """
        for rec in self:
            if rec.cfdi_type != "recibidos":
                continue
            doc = rec.cfdi_document_id
            if not doc:
                # Re-trigger pipeline once on demand; the attachment hook
                # may have been skipped (install_mode, _skip_cfdi_*, etc).
                if rec.attachment_id:
                    rec.attachment_id.sudo()._trigger_cfdi_compliance_pipeline()
                    rec._compute_cfdi_document_id()
                    doc = rec.cfdi_document_id
            if not doc:
                continue
            if doc.compliance_state in _BLOCKING_STATES and not self.env.context.get(
                "_cfdi_compliance_force",
            ):
                raise UserError(_(
                    "No se puede importar la factura del CFDI %(uuid)s.\n"
                    "Estado de Compliance: %(state)s (score %(score)s/100).\n\n"
                    "Solicite a un autorizador que ejecute 'Autorizar Override' "
                    "en el documento de Compliance.",
                ) % {
                    "uuid": rec.name or "",
                    "state": doc.compliance_state,
                    "score": doc.compliance_score,
                })
        result = super().action_import_invoice()
        # Propagate compliance link to the freshly-created account.move
        for rec in self:
            if rec.invoice_id and rec.cfdi_document_id:
                # Use sudo to avoid ACL hiccups on cross-module fields
                rec.invoice_id.sudo().write({
                    "cfdi_document_id": rec.cfdi_document_id.id,
                })
                # Reverse-link from cfdi.document to the move
                if not rec.cfdi_document_id.related_move_id:
                    rec.cfdi_document_id.sudo().with_context(
                        _audit_internal_write=True,
                    ).write({"related_move_id": rec.invoice_id.id})
        return result
