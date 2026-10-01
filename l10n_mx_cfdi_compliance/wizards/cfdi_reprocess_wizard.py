# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from odoo import fields, models


class CfdiReprocessWizard(models.TransientModel):
    _name = "l10n_mx.cfdi.reprocess.wizard"
    _description = "Reprocesar Compliance de CFDIs"

    document_ids = fields.Many2many("l10n_mx.cfdi.document", required=True)
    profile_id = fields.Many2one(
        "l10n_mx.compliance.profile",
        help="Si se especifica, se aplica este perfil; si no, se usa la "
             "resolucion estandar (override por factura, partner o compania).",
    )
    force = fields.Boolean(
        string="Forzar reprocesamiento",
        help="Si esta activo, reprocesa aun documentos en estado 'authorized'.",
    )

    def action_reprocess(self):
        for doc in self.document_ids:
            if not self.force and doc.compliance_state == "authorized":
                continue
            if self.profile_id:
                doc.profile_id = self.profile_id
            doc._run_compliance_pipeline()
        return {"type": "ir.actions.act_window_close"}
