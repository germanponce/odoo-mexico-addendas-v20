# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ComplianceProfile(models.Model):
    _name = "l10n_mx.compliance.profile"
    _description = "Perfil de Compliance CFDI"
    _check_company_auto = True
    _order = "company_id, sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    is_default = fields.Boolean(string="Default for company")
    company_id = fields.Many2one(
        "res.company", required=True,
        default=lambda s: s.env.company, index=True,
    )
    fiscal_regime = fields.Selection([
        ("general", "General de Ley Personas Morales (601)"),
        ("coordinados", "Coordinados (624)"),
        ("agapes", "AGAPES (622)"),
        ("resico", "Regimen Simplificado de Confianza (626)"),
        ("grupo", "Opcional Grupos de Sociedades (623)"),
        ("other", "Otro"),
    ], default="general")
    description = fields.Text(translate=True)
    rule_config_ids = fields.One2many(
        "l10n_mx.compliance.rule.config", "profile_id",
        string="Reglas configuradas", copy=True,
    )
    min_score_pass = fields.Integer(
        default=80,
        help="Score minimo a partir del cual el CFDI se considera aprobado limpio.",
    )
    min_score_warning = fields.Integer(
        default=60,
        help="Score minimo aceptable con advertencias; debajo se considera bloqueado.",
    )
    transition_mode = fields.Boolean(
        string="Modo Transicion",
        help="Mientras este activo, las reglas marcadas como 'error' se degradan a "
             "'warning'. Util para onboarding.",
    )
    rule_count = fields.Integer(compute="_compute_rule_count")

    _code_company_uniq = models.Constraint(
        "UNIQUE(code, company_id)",
        "El codigo del perfil debe ser unico por compania.",
    )

    @api.depends("rule_config_ids")
    def _compute_rule_count(self):
        for r in self:
            r.rule_count = len(r.rule_config_ids)

    @api.constrains("min_score_pass", "min_score_warning")
    def _check_thresholds(self):
        for r in self:
            if not (0 <= r.min_score_warning <= r.min_score_pass <= 100):
                raise ValidationError(_(
                    "Los umbrales deben cumplir: 0 <= warning (%s) <= pass (%s) <= 100"
                ) % (r.min_score_warning, r.min_score_pass))

    @api.constrains("is_default", "company_id", "active")
    def _check_single_default(self):
        for r in self.filtered(lambda x: x.is_default and x.active):
            other = self.search([
                ("is_default", "=", True),
                ("active", "=", True),
                ("company_id", "=", r.company_id.id),
                ("id", "!=", r.id),
            ], limit=1)
            if other:
                raise ValidationError(_(
                    "Ya existe un perfil por defecto activo para la compania %s: %s"
                ) % (r.company_id.display_name, other.name))

    def action_populate_all_rules(self):
        """Crea registros rule_config para TODAS las reglas del catalogo
        que no esten ya configuradas en el perfil."""
        Cfg = self.env["l10n_mx.compliance.rule.config"]
        Rule = self.env["l10n_mx.compliance.rule"]
        for profile in self:
            existing_rules = profile.rule_config_ids.mapped("rule_id")
            for rule in Rule.search([]) - existing_rules:
                Cfg.create({
                    "profile_id": profile.id,
                    "rule_id": rule.id,
                    "enabled": True,
                    "severity": rule.default_severity,
                    "weight": rule.default_weight,
                })
        return True

    def name_get(self):
        return [(r.id, f"[{r.code}] {r.name}") for r in self]
