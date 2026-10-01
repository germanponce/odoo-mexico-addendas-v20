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

    x_tony_code = fields.Char(string="Codigo Tony",compute="_compute_x_tony_code",inverse="_set_x_tony_code", store=True)

    @api.depends('product_variant_ids.x_tony_code')
    def _compute_x_tony_code(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.x_tony_code = template.product_variant_ids.x_tony_code
        for template in (self - unique_variants):
            template.x_tony_code = False

    def _set_x_tony_code(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.x_tony_code = self.x_tony_code

class AddendaSale(models.Model):
    """docstring for AddendaFields"""
    _inherit = 'sale.order'

    addenda_type = fields.Selection(selection_add=[('bovadd', 'Tony BOVEDAFISCAL')], ondelete={'bovadd': 'set null'}) 

    l10n_mx_edi_addenda_bovedafiscal_no_pedido = fields.Char(string='Numero de pedido')

    l10n_mx_edi_addenda_bovedafiscal_peso = fields.Float(string='Peso')

    l10n_mx_edi_addenda_bovedafiscal_cantidad_bultos = fields.Float(string='Cantidad Bultos')


class AccountMove(models.Model):
    _inherit = 'account.move'
        

    def l10n_mx_edi_amece_is_required(self):
        addenda_amece = self.env.ref('l10n_mx_addenda_amece.l10n_mx_edi_addenda_amece', raise_if_not_found=False)
        addenda = (self.partner_id.l10n_mx_edi_addenda or self.partner_id.commercial_partner_id.l10n_mx_edi_addenda)
        return (True if addenda.id == addenda_amece.id else False)

    addenda_type = fields.Selection(selection_add=[('bovadd', 'Tony BOVEDAFISCAL')], ondelete={'bovadd': 'set null'}) 

    l10n_mx_edi_addenda_bovedafiscal_no_pedido = fields.Char(string='Numero de pedido')

    l10n_mx_edi_addenda_bovedafiscal_peso = fields.Float(string='Peso')

    l10n_mx_edi_addenda_bovedafiscal_cantidad_bultos = fields.Float(string='Cantidad Bultos')

    @api.model
    def create(self, vals):
        res = super(AccountMove, self).create(vals)
        if res.move_type == 'out_invoice':
            sale_model = 'sale_line_ids' in res.invoice_line_ids._fields
            sale_id = res.mapped('invoice_line_ids.sale_line_ids.order_id') if sale_model else False
            if sale_id:
                res.addenda_type = sale_id.addenda_type
                res.l10n_mx_edi_addenda_bovedafiscal_no_pedido = sale_id.l10n_mx_edi_addenda_bovedafiscal_no_pedido
                res.l10n_mx_edi_addenda_bovedafiscal_peso = sale_id.l10n_mx_edi_addenda_bovedafiscal_peso
                res.l10n_mx_edi_addenda_bovedafiscal_cantidad_bultos = sale_id.l10n_mx_edi_addenda_bovedafiscal_cantidad_bultos
        return res

class AddendaOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    addenda_type = fields.Selection(selection_add=[('bovadd', 'Tony BOVEDAFISCAL')], ondelete={'bovadd': 'set null'}) 


class AccountInvoiceLine(models.Model):
    _inherit = 'account.move.line'

