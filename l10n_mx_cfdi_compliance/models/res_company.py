# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    default_compliance_profile_id = fields.Many2one(
        "l10n_mx.compliance.profile",
        string="Perfil de Compliance por defecto",
        domain="[('company_id','=',id)]",
    )
    is_coordinados_controladora = fields.Boolean(
        string="Es Controladora (Coordinados)",
    )
    coordinado_relation_ids = fields.One2many(
        "l10n_mx.cfdi.coordinado.relation", "controladora_company_id",
    )
    cfdi_compliance_async_threshold_kb = fields.Integer(
        default=1024,
        help="Tamano en KB a partir del cual el pipeline se ejecuta en background "
             "(requiere un planificador asincrono externo, p.ej. queue_job).",
    )

    @api.model
    def _l10n_mx_cfdi_create_default_profile(self):
        """Crea un perfil 'standard' por compania si aun no existe.

        Marca el perfil como ``transition_mode=True`` para no bloquear
        operativamente al cliente desde el primer dia: todas las reglas
        marcadas como ``error`` se degradan a ``warning`` hasta que el
        cliente lo apague manualmente.
        """
        Profile = self.env["l10n_mx.compliance.profile"].sudo()
        Cfg = self.env["l10n_mx.compliance.rule.config"].sudo()
        Rule = self.env["l10n_mx.compliance.rule"].sudo()
        for company in self.search([]):
            existing = Profile.search([
                ("company_id", "=", company.id),
                ("code", "=", "STANDARD"),
            ], limit=1)
            if existing:
                profile = existing
            else:
                profile = Profile.create({
                    "name": "Estandar (Transicion)",
                    "code": "STANDARD",
                    "company_id": company.id,
                    "fiscal_regime": "general",
                    "is_default": True,
                    "transition_mode": True,
                    "min_score_pass": 80,
                    "min_score_warning": 60,
                    "description": (
                        "Perfil por defecto creado al instalar el modulo. "
                        "Modo transicion activado: las reglas 'error' se degradan "
                        "a 'warning' hasta que se desactive manualmente."
                    ),
                })
                if not company.default_compliance_profile_id:
                    company.default_compliance_profile_id = profile.id
            existing_rules = profile.rule_config_ids.mapped("rule_id")
            for rule in Rule.search([("is_active_in_registry", "=", True)]):
                if rule in existing_rules:
                    continue
                Cfg.create({
                    "profile_id": profile.id,
                    "rule_id": rule.id,
                    "enabled": True,
                    "severity": rule.default_severity,
                    "weight": rule.default_weight,
                })
        return True
