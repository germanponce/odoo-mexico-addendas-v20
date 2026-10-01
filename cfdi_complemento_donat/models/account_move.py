# -*- encoding: utf-8 -*-
# Coded by German Ponce Dominguez 
#     ▬▬▬▬▬.◙.▬▬▬▬▬  
#       ▂▄▄▓▄▄▂  
#    ◢◤█▀▀████▄▄▄▄▄▄ ◢◤  
#    █▄ █ █▄ ███▀▀▀▀▀▀▀ ╬  
#    ◥ █████ ◤  
#     ══╩══╩═  
#       ╬═╬  
#       ╬═╬ Dream big and start with something small!!!  
#       ╬═╬  
#       ╬═╬ You can do it!  
#       ╬═╬   Let's go...
#    ☻/ ╬═╬   
#   /▌  ╬═╬   
#   / \
# Cherman Seingalt - german.ponce@outlook.com

from lxml.objectify import fromstring
from odoo import api, fields, models

from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    complemento_donaciones = fields.Boolean(
        'Complemento - Donatarias',
        help='Use this field when the invoice require the complement to '
        '"Donations". This value will be used to indicate the use of the '
        'information from the document that authorize to receive '
        'deductible donations, granted by SAT')


    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id.complemento_donaciones:
            self.complemento_donaciones = True
        return super()._onchange_partner_id()

    @api.model
    def create(self, vals):
        if vals.get('partner_id'):
            partner = self.env['res.partner'].browse(vals['partner_id'])
            if partner.complemento_donaciones:
                vals.update({
                                'complemento_donaciones': True,
                            })
        return super().create(vals)


    def _l10n_mx_edi_add_invoice_cfdi_values(self, cfdi_values, percentage_paid=None, global_invoice=False):
        # EXTENDS 'l10n_mx_edi'
        self.ensure_one()
        super()._l10n_mx_edi_add_invoice_cfdi_values(cfdi_values, percentage_paid=percentage_paid, global_invoice=global_invoice)
        if cfdi_values.get('errors'):
            return
        if self.complemento_donaciones:
            cfdi_values['complemento_donaciones'] = True
        else:
            cfdi_values['complemento_donaciones'] = False
        cfdi_values['noAutorizacion'] = self.company_id.l10n_mx_edi_donat_auth or '01'
        cfdi_values['fechaAutorizacion'] = self.company_id.l10n_mx_edi_donat_date or '02'
        cfdi_values['leyenda'] = self.company_id.l10n_mx_edi_donat_note or '03'