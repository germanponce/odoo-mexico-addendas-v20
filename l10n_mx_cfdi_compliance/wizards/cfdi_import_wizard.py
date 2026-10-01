# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
"""Mass import wizard. Accepts multiple XML attachments and processes
them sequentially (or in batches), producing one CFDI document each.
"""
import base64
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CfdiImportWizard(models.TransientModel):
    _name = "l10n_mx.cfdi.import.wizard"
    _description = "Importacion Masiva de CFDIs"

    attachment_ids = fields.Many2many(
        "ir.attachment", string="Archivos XML",
    )
    line_ids = fields.One2many(
        "l10n_mx.cfdi.import.wizard.line", "wizard_id", readonly=True,
    )
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, required=True,
    )
    auto_run_pipeline = fields.Boolean(default=True)
    state = fields.Selection([
        ("draft", "Draft"), ("done", "Done"),
    ], default="draft")

    def action_import(self):
        self.ensure_one()
        if not self.attachment_ids:
            raise UserError(_("No se seleccionaron archivos."))
        Doc = self.env["l10n_mx.cfdi.document"].sudo()
        Line = self.env["l10n_mx.cfdi.import.wizard.line"].sudo()
        for att in self.attachment_ids:
            try:
                if not att._is_cfdi_xml():
                    Line.create({"wizard_id": self.id, "attachment_id": att.id,
                                 "status": "skipped",
                                 "message": "No es CFDI XML"})
                    continue
                doc = Doc._create_from_attachment(att, company=self.company_id)
                if self.auto_run_pipeline:
                    doc._run_compliance_pipeline()
                Line.create({
                    "wizard_id": self.id, "attachment_id": att.id,
                    "document_id": doc.id, "status": "ok",
                    "message": f"Estado: {doc.compliance_state}, "
                               f"score {doc.compliance_score}",
                })
            except Exception as e:  # noqa: BLE001
                _logger.exception("Mass import failed for %s", att.name)
                Line.create({
                    "wizard_id": self.id, "attachment_id": att.id,
                    "status": "error", "message": str(e),
                })
        self.state = "done"
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name, "res_id": self.id,
            "view_mode": "form", "target": "new",
        }


class CfdiImportWizardLine(models.TransientModel):
    _name = "l10n_mx.cfdi.import.wizard.line"
    _description = "Linea de Importacion CFDI"

    wizard_id = fields.Many2one("l10n_mx.cfdi.import.wizard", ondelete="cascade")
    attachment_id = fields.Many2one("ir.attachment")
    document_id = fields.Many2one("l10n_mx.cfdi.document")
    status = fields.Selection([
        ("ok", "OK"), ("skipped", "Omitido"), ("error", "Error"),
    ])
    message = fields.Text()
