# -*- coding: utf-8 -*-

# Part of Probuse Consulting Service Pvt Ltd. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"
    
    custom_allow_send_mail = fields.Boolean(
        string='Envio de Pago Automatico', 
        copy=True,
        help='If you checkbox then customer will get payment receipt automatically by email on validation of Payment.'
    )
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
