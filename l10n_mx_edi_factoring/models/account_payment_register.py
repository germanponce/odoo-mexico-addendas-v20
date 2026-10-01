# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    x_factoring_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Factorante financiero',
        domain=[('x_is_factoring_partner', '=', True)],
        help='Factorante al que se emite el CFDI de Pago cuando hay factoraje.',
    )
