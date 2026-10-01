# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from .compliance_rule import SEVERITY_SELECTION


class ComplianceRuleConfig(models.Model):
    _name = "l10n_mx.compliance.rule.config"
    _description = "Configuracion de Regla por Perfil"
    _order = "profile_id, sequence, id"
    _check_company_auto = True

    profile_id = fields.Many2one(
        "l10n_mx.compliance.profile", required=True,
        ondelete="cascade", index=True,
    )
    company_id = fields.Many2one(
        "res.company", related="profile_id.company_id",
        store=True, readonly=True,
    )
    rule_id = fields.Many2one(
        "l10n_mx.compliance.rule", required=True, ondelete="restrict",
        domain=[("is_active_in_registry", "=", True)],
    )
    rule_code = fields.Char(related="rule_id.code", store=True, readonly=True)
    rule_category = fields.Selection(
        related="rule_id.category", store=True, readonly=True,
    )
    sequence = fields.Integer(default=10)
    enabled = fields.Boolean(default=True)
    severity = fields.Selection(
        SEVERITY_SELECTION, required=True, default="warning",
    )
    weight = fields.Integer(
        default=10,
        help="Peso del impacto en el calculo del score (1-100).",
    )
    authorizer_group_id = fields.Many2one(
        "res.groups",
        help="Grupo autorizado a hacer override de esta regla. "
             "Si esta vacio, se usa el grupo CFDI Compliance Authorizer por defecto.",
    )
    params = fields.Json(
        help="Parametros JSON especificos de la regla (umbrales, listas, etc.)",
    )
    notes = fields.Text()

    _rule_profile_uniq = models.Constraint(
        "UNIQUE(profile_id, rule_id)",
        "La regla ya esta configurada en este perfil.",
    )

    @api.constrains("weight")
    def _check_weight(self):
        for r in self:
            if not (1 <= r.weight <= 100):
                raise ValidationError(_("El peso debe estar entre 1 y 100."))
