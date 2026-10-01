# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class CfdiOverrideWizard(models.TransientModel):
    _name = "l10n_mx.cfdi.override.wizard"
    _description = "Autorizar Override de CFDI Compliance"

    document_id = fields.Many2one(
        "l10n_mx.cfdi.document", required=True, readonly=True,
    )
    result_ids = fields.Many2many(
        "l10n_mx.compliance.result",
        string="Reglas a sobrescribir",
        domain="[('document_id','=',document_id),('passed','=',False)]",
    )
    reason = fields.Text(
        required=True,
        help="Razon comercial / fiscal del override (minimo 30 caracteres).",
    )
    confirm_understanding = fields.Boolean(
        string="Entiendo el riesgo fiscal y asumo la responsabilidad",
    )

    @api.constrains("reason")
    def _check_reason(self):
        for w in self:
            if not w.reason or len(w.reason.strip()) < 30:
                raise ValidationError(_(
                    "La razon debe tener al menos 30 caracteres."
                ))

    def action_apply(self):
        self.ensure_one()
        if not self.confirm_understanding:
            raise UserError(_("Debe confirmar el entendimiento del riesgo."))
        if not self.env.user.has_group(
                "l10n_mx_cfdi_compliance.group_cfdi_compliance_authorizer"):
            raise UserError(_("No tiene permisos de autorizador."))
        if not self.result_ids:
            raise UserError(_("Seleccione al menos una regla a sobrescribir."))
        now = fields.Datetime.now()
        self.result_ids.write({
            "overridden": True,
            "override_user_id": self.env.user.id,
            "override_reason": self.reason,
            "override_date": now,
        })
        # Re-evaluate document state: if no remaining non-overridden errors,
        # promote to authorized.
        doc = self.document_id
        remaining = doc.result_ids.filtered(
            lambda r: not r.passed and not r.overridden
            and r.severity in ("error", "authorization")
        )
        if not remaining:
            doc.compliance_state = "authorized"
        self.env["l10n_mx.compliance.audit.log"].sudo().log(
            "override", document=doc,
            payload={
                "by": self.env.user.login,
                "reason": self.reason,
                "rules": self.result_ids.mapped("rule_code"),
            },
        )
        return {"type": "ir.actions.act_window_close"}
