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

    addenda_type = fields.Selection(selection_add=[('amazon', 'Amazon')], ondelete={'amazon': 'set null'}) 

    orden_compra_amazon = fields.Char(string='Numero de la Orden de Compra')

    notas_amazon = fields.Text('Comentarios para la Addenda')

class AccountMove(models.Model):
    _inherit = 'account.move'
        

    addenda_type = fields.Selection(selection_add=[('amazon', 'Amazon')], ondelete={'amazon': 'set null'}) 

    orden_compra_amazon = fields.Char(string='Numero de la Orden de Compra')

    notas_amazon = fields.Text('Comentarios para la Addenda')

    @api.model
    def create(self, vals):
        res = super(AccountMove, self).create(vals)
        if res.move_type == 'out_invoice':
            sale_model = 'sale_line_ids' in res.invoice_line_ids._fields
            sale_id = res.mapped('invoice_line_ids.sale_line_ids.order_id') if sale_model else False
            if sale_id:
                res.addenda_type = sale_id.addenda_type
                res.orden_compra_amazon = sale_id.orden_compra_amazon
                res.notas_amazon = sale_id.notas_amazon
                for line in res.invoice_line_ids:
                    no_identificacion_amazon = str(line.quantity)+" "+line.product_uom_id.name
                    line.no_identificacion_amazon = no_identificacion_amazon
        return res

class AddendaOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    addenda_type = fields.Selection(selection_add=[('amazon', 'AstraZeneca')], ondelete={'amazon': 'set null'}) 


class AccountInvoiceLine(models.Model):
    _inherit = 'account.move.line'


    no_identificacion_amazon = fields.Char('No. Identificacion Addenda (Amazon)')

    @api.onchange('product_id','quantity')
    def onchange_no_identificacion_amazon(self):
        if self.product_id:
            #no_identificacion_amazon = str(self.quantity)+" "+self.product_uom_id.name
            no_identificacion_amazon = self.product_id.default_code
            self.no_identificacion_amazon = no_identificacion_amazon
