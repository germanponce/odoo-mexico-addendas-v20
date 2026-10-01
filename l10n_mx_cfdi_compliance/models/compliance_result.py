# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from odoo import api, fields, models

from .compliance_rule import SEVERITY_SELECTION


class ComplianceResult(models.Model):
    _name = "l10n_mx.compliance.result"
    _description = "Resultado de Regla de Compliance"
    _order = "document_id, sequence, severity desc"

    document_id = fields.Many2one(
        "l10n_mx.cfdi.document", required=True,
        ondelete="cascade", index=True,
    )
    company_id = fields.Many2one(
        related="document_id.company_id", store=True, readonly=True, index=True,
    )
    rule_id = fields.Many2one(
        "l10n_mx.compliance.rule", required=True, ondelete="restrict",
    )
    rule_code = fields.Char(related="rule_id.code", store=True, index=True)
    # rule.name es translate=True; un related stored+translate causa warning
    # "Translated stored related field will not be computed correctly". Como
    # el campo solo se usa en views (display), lo dejamos NO stored — Odoo
    # lo resuelve al vuelo desde rule_id.name respetando el idioma actual.
    rule_name = fields.Char(related="rule_id.name")
    rule_category = fields.Selection(related="rule_id.category", store=True)
    severity = fields.Selection(SEVERITY_SELECTION, required=True)
    passed = fields.Boolean(default=False, index=True)
    message = fields.Text()
    details = fields.Json()
    execution_ms = fields.Integer()
    sequence = fields.Integer(default=10)
    score_impact = fields.Integer()
    # Override
    overridden = fields.Boolean()
    override_user_id = fields.Many2one("res.users")
    override_reason = fields.Text()
    override_date = fields.Datetime()

    severity_color = fields.Integer(compute="_compute_severity_color")

    @api.depends("severity", "passed", "overridden")
    def _compute_severity_color(self):
        for r in self:
            if r.passed:
                r.severity_color = 10  # green
            elif r.overridden:
                r.severity_color = 4   # orange (overridden)
            elif r.severity == "info":
                r.severity_color = 7
            elif r.severity == "warning":
                r.severity_color = 3   # yellow
            elif r.severity == "authorization":
                r.severity_color = 5   # purple
            else:
                r.severity_color = 1   # red
