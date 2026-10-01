# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RetentionTypeTaxPayer(models.Model):
    _name = 'retention.type.taxpayer'
    _description = 'Tipo Contribuyente Sujeto a Retencion'
    _rec_name = 'name'
    _order = 'code'

    code = fields.Char(
        string='Code',
        required=True,
    )

    name = fields.Char(
        string='Name',
        required=True,
    )

    @api.constrains('code')
    def _constraint_code_other_records(self):
        for rec in self:
            other_ids = self.search([
                ('code', '=', rec.code),
                ('id', '!=', rec.id)
            ], limit=1)

            if other_ids:
                raise ValidationError(
                    "El código debe ser único."
                )

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for rec in self:
            if rec.code and rec.name:
                rec.display_name = '[ %s ] %s' % (
                    rec.code,
                    rec.name
                )
            else:
                rec.display_name = rec.name