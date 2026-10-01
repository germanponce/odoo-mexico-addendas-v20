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


from os.path import join
from odoo.tools import float_round
from odoo.exceptions import UserError
from odoo import _, api, fields, models, tools

from odoo.tools.xml_utils import _check_with_xsd
from odoo.tools.float_utils import float_round, float_is_zero
from odoo.tools.float_utils import float_repr

import logging
import re
import base64
import json
import requests
import random
import string

from lxml import etree
from lxml.objectify import fromstring
from datetime import datetime
from io import BytesIO
from zeep import Client
from zeep.transports import Transport
from json.decoder import JSONDecodeError

class ResCompany(models.Model):
    _inherit = 'res.partner'


class AddendaProduct(models.Model):
    _inherit = 'product.template'

class AddendaSale(models.Model):
    """docstring for AddendaFields"""
    _inherit = 'sale.order'

    addenda_type = fields.Selection(selection_add=[('astra_zeneca', 'AstraZeneca')], ondelete={'astra_zeneca': 'set null'}) 

    orden_compra_astra_zeneca = fields.Char(string='Numero de la Orden de Compra')


class AccountMove(models.Model):
    _inherit = 'account.move'
        

    addenda_type = fields.Selection(selection_add=[('astra_zeneca', 'AstraZeneca')], ondelete={'astra_zeneca': 'set null'}) 

    orden_compra_astra_zeneca = fields.Char(string='Numero de la Orden de Compra')

    @api.model
    def create(self, vals):
        res = super(AccountMove, self).create(vals)
        if res.move_type == 'out_invoice':
            sale_model = 'sale_line_ids' in res.invoice_line_ids._fields
            sale_id = res.mapped('invoice_line_ids.sale_line_ids.order_id') if sale_model else False
            if sale_id:
                res.addenda_type = sale_id.addenda_type
                res.orden_compra_astra_zeneca = sale_id.orden_compra_astra_zeneca
                for line in res.invoice_line_ids:
                    no_identificacion_astra_zeneca = str(line.quantity)+" "+line.product_uom_id.name
                    line.no_identificacion_astra_zeneca = no_identificacion_astra_zeneca
        return res

    def _l10n_mx_edi_add_invoice_cfdi_values(self, cfdi_values):
        # EXTENDS 'l10n_mx_edi'
        super()._l10n_mx_edi_add_invoice_cfdi_values(cfdi_values)
 
        if self.addenda_type != 'astra_zeneca' or cfdi_values.get('errors'):
            return
 
        for base_line in cfdi_values.get('base_lines', []):
            invl = base_line.get('record')
            no_identificacion = invl and invl.no_identificacion_astra_zeneca
            if invl.move_id.addenda_type == 'astra_zeneca':
                if no_identificacion:
                    base_line['l10n_mx_cfdi_values']['no_identificacion'] = no_identificacion
 
class AddendaOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    addenda_type = fields.Selection(selection_add=[('astra_zeneca', 'AstraZeneca')], ondelete={'astra_zeneca': 'set null'}) 


class AccountInvoiceLine(models.Model):
    _inherit = 'account.move.line'


    no_identificacion_astra_zeneca = fields.Char('No. Identificacion Addenda')

    @api.onchange('product_id','quantity')
    def onchange_no_identificacion_astra_zeneca(self):
        if self.product_id:
            #no_identificacion_astra_zeneca = str(self.quantity)+" "+self.product_uom_id.name
            no_identificacion_astra_zeneca = self.product_id.default_code
            self.no_identificacion_astra_zeneca = no_identificacion_astra_zeneca
