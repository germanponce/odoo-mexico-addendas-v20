# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CoordinadoRelation(models.Model):
    _name = "l10n_mx.cfdi.coordinado.relation"
    _description = "Relacion Fiscal Coordinados / AGAPES / Grupo"
    _check_company_auto = True
    _order = "controladora_company_id, valid_from desc"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    controladora_company_id = fields.Many2one(
        "res.company", required=True, index=True,
        string="Compania Controladora",
        default=lambda s: s.env.company,
    )
    coordinada_company_id = fields.Many2one(
        "res.company", string="Compania Coordinada (en Odoo)",
        help="Si la coordinada existe como compania en Odoo, indicarla aqui.",
    )
    coordinada_partner_id = fields.Many2one(
        "res.partner", string="Partner Coordinado",
        help="Alternativa cuando la coordinada NO existe como compania en Odoo.",
    )
    coordinada_vat = fields.Char(
        string="RFC Coordinada", required=True, index=True,
    )
    relation_type = fields.Selection([
        ("coordinados", "Regimen de Coordinados (Art. 72-73 LISR)"),
        ("agapes", "AGAPES Integradora"),
        ("grupo_optativo", "Regimen Opcional para Grupos de Sociedades"),
        ("mandato", "Mandato Mercantil"),
    ], required=True, default="coordinados")
    valid_from = fields.Date(required=True)
    valid_to = fields.Date()
    accept_cfdi_to_coordinada = fields.Boolean(
        default=True,
        help="Permite que CFDIs cuyo receptor sea esta coordinada sean aceptados "
             "por la controladora como deducibles.",
    )
    require_distribution_record = fields.Boolean(
        default=True,
        help="Exige registrar la distribucion del gasto entre coordinadas.",
    )
    legal_document_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Convenio / Documento Legal",
        help="PDF del convenio, acta o resolucion que respalda la relacion.",
    )
    notes = fields.Text()

    _coord_unique = models.Constraint(
        "UNIQUE(controladora_company_id, coordinada_vat, valid_from)",
        "Ya existe esta relacion para el periodo.",
    )

    @api.constrains("valid_from", "valid_to")
    def _check_dates(self):
        for r in self:
            if r.valid_to and r.valid_to < r.valid_from:
                raise ValidationError(_("valid_to no puede ser anterior a valid_from."))

    @api.constrains("coordinada_vat")
    def _check_vat(self):
        for r in self:
            vat = (r.coordinada_vat or "").strip()
            if not vat or len(vat) < 12:
                raise ValidationError(_("RFC de coordinada invalido."))

    @staticmethod
    def _normalize_vat_vals(vals):
        if vals.get("coordinada_vat"):
            vals["coordinada_vat"] = vals["coordinada_vat"].upper().strip()
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._normalize_vat_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._normalize_vat_vals(vals)
        return super().write(vals)

    @api.onchange("coordinada_company_id")
    def _onchange_coordinada_company(self):
        if self.coordinada_company_id and self.coordinada_company_id.vat:
            self.coordinada_vat = self.coordinada_company_id.vat
