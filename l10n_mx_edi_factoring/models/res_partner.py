# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_is_factoring_partner = fields.Boolean(
        string='Factorante',
        help='Indica que este contacto es un factorante financiero.',
    )
    x_factoring_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Factorante financiero',
        domain=[('x_is_factoring_partner', '=', True)],
        help='Factorante financiero asociado a este cliente.',
    )
