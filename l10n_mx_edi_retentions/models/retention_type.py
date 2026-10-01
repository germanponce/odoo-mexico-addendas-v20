# -*- coding: utf-8 -*-

from odoo import fields, models, api


class RetentionType(models.Model):

    _name = 'retention.type'
    _description = 'Retention CFDI Type'
    _rec_name = 'name'
    _order = 'code'

    code = fields.Char(
        string='Code',
        required=True,
        help='Clave de retención según catálogo del SAT (p.ej. 14 = Dividendos).',
    )
    name = fields.Char(
        string='Name',
        required=True,
        help='Descripción del tipo de retención.',
    )

    # _sql_constraints = [
    #     ('code_unique', 'unique(code)', 'Ya existe un tipo de retención con ese código.'),
    # ]


    @api.constrains('code','name')
    def _constraint_code_other_records(self):
        for rec in self:
            other_ids = self.search([('code','=',rec.code),('id','!=',rec.id)])
            if other_ids:
                raise ValidationError("El código debe ser unico.")
        return True

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for rec in self:
            if rec.code and rec.name:
                name = '[ '+rec.code + ' ] ' + rec.name
            else:
                name = rec.name
            rec.display_name = name