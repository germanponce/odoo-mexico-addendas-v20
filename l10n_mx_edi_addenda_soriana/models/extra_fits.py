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

    x_gln = fields.Char(string='GLN', store=True, help='Global Location Number')
    x_center = fields.Char(string='Entrega de Mercancía', store=True, help="Customer Store")
    x_partner_code = fields.One2many('res.partner.supplierinfo', 'name', 'Códigos de Vendedores')
    x_product_info = fields.One2many('product.supplierinfo.sale', 'partner_name', 'Extra Info Productos')
    x_edi_identification = fields.Char(string="Identificador EDI", store=True, help="Identificador EDI del contacto")

    x_vendor_code = fields.Char(string="Código de Vendedor")

    x_vendor_supplier_code = fields.Char(string="Código de Proveedor (Soriana)")

class ProductSupplierinfoSale(models.Model):
    _name = 'product.supplierinfo.sale' 
    _description = 'Relation between product info from customer'
    _rec_name = "product_name"
    
    partner_name = fields.Many2one('res.partner', ondelete='cascade', required=True)
    product_name = fields.Many2one('product.template', ondelete='cascade', required=True)     
    product_code = fields.Char(string='Código de producto', help='Code that customer know the product')
    uom = fields.Char(string='UdM', help='Unit Of Measurement')
    uom_additional = fields.Char(string='UdM Adicional', help='Unit Of Measurement Additional')
    company = fields.Many2one('res.company','Compañia', default=lambda self: self.env.company)
    vendor_code = fields.Char(string="Código de proveedor", help="Code of the vendor assigned by the customer")

class ResPartnerSupplierinfo(models.Model):
    _name = 'res.partner.supplierinfo'
    _description = 'Indlude additional information about partner'
    
    name = fields.Many2one(
        'res.partner',
        ondelete='cascade', required=True)
    companies = fields.Many2one('res.company','Compañia', default=lambda self: self.env.company)
    code = fields.Char(string='Código de vendedor')

class AddendaProduct(models.Model):
    _inherit = 'product.template'

    x_product_supplierinfo = fields.One2many('product.supplierinfo.sale', 'product_name')
    x_codigo_soriana = fields.Char('Codigo Soriana')

class AddendaSale(models.Model):
    """docstring for AddendaFields"""
    _inherit = 'sale.order'

    addenda_type = fields.Selection(selection_add=[('soriana_descarga', 'Soriana (Descarga Remision)')], ondelete={'soriana_descarga': 'set null'}) 

    x_order_reference = fields.Char(string="Folio del Pedido", store=True,
                                   help='Specifies the purchase order reference (Buyer) that the invoice refers to.')
    
    x_order_reference_date = fields.Date(string='Fecha de Remisión', store=True,
                                         help='Specifies the purchase order date (Buyer) that the invoice refers to.')
    x_additional_reference = fields.Char(string='Referencia Adicional', store=True,
                                         help='Aproval Number')
    x_delivery_reference = fields.Char(string='Número de cita', store=True,
                                       help='Folio number. Number issued by the buyer when he reviews the merchandise that is invoiced')
    x_delivery_reference_date = fields.Date(string='Fecha de Entrega', store=True,
                                            help='Specifies the date the receipt folio number was assigned.')
    x_vendor_code = fields.Char(string="Código de vendedor", related="partner_id.x_vendor_code")
    x_vendor_supplier_code = fields.Char(string="Código de Proveedor", related="partner_id.x_vendor_supplier_code", readonly=False)

    x_gln = fields.Char(string='GLN', store=True, help='Global Location Number', related="partner_id.x_gln", readonly=False)
    x_center = fields.Char(string='Entrega de Mercancía', store=True, help="Customer Store", related="partner_id.x_center", readonly=False)

    x_order_remision = fields.Char(string="Remision")

    x_cedis_id = fields.Many2one('soriana.cedis.code', 'Tienda de la Remisión')

    x_cantidad_bultos = fields.Integer('Cantidad Bultos')

    x_tipo_moneda = fields.Char('Tipo de Moneda', default="1")
    x_tipo_bulto = fields.Char('Tipo de Bulto', default="1")

class AccountMove(models.Model):
    _inherit = 'account.move'
        
    addenda_type = fields.Selection(selection_add=[('soriana_descarga', 'Soriana (Descarga Remision)')], ondelete={'soriana_descarga': 'set null'}) 

    x_order_reference = fields.Char(string="Folio del Pedido", store=True,
                                   help='Specifies the purchase order reference (Buyer) that the invoice refers to.')
    
    x_order_reference_date = fields.Date(string='Fecha de Remisión', store=True,
                                         help='Specifies the purchase order date (Buyer) that the invoice refers to.')
    x_additional_reference = fields.Char(string='Referencia Adicional', store=True,
                                         help='Aproval Number')
    x_delivery_reference = fields.Char(string='Número de cita', store=True,
                                       help='Folio number. Number issued by the buyer when he reviews the merchandise that is invoiced')
    x_delivery_reference_date = fields.Date(string='Fecha de Entrega', store=True,
                                            help='Specifies the date the receipt folio number was assigned.')
    x_vendor_code = fields.Char(string="Código de vendedor", related="partner_id.x_vendor_code")

    x_vendor_supplier_code = fields.Char(string="Código de Proveedor", related="partner_id.x_vendor_supplier_code")

    x_gln = fields.Char(string='GLN', store=True, help='Global Location Number', related="partner_id.x_gln", readonly=False)
    x_center = fields.Char(string='Entrega de Mercancía', store=True, help="Customer Store", related="partner_id.x_center", readonly=False)

    x_entrega_mercancia = fields.Char(string='Entrega de Mercancía', store=True, help="Entrega de Mercancía")

    x_order_remision = fields.Char(string="Remision")

    x_cedis_id = fields.Many2one('soriana.cedis.code', 'Tienda de la Remisión')

    x_cantidad_bultos = fields.Integer('Cantidad Bultos')

    x_tipo_moneda = fields.Char('Tipo de Moneda', default="1")
    x_tipo_bulto = fields.Char('Tipo de Bulto', default="1")

    @api.model
    def create(self, vals):
        res = super(AccountMove, self).create(vals)
        if res.move_type == 'out_invoice':
            sale_model = 'sale_line_ids' in res.invoice_line_ids._fields
            sale_id = res.mapped('invoice_line_ids.sale_line_ids.order_id') if sale_model else False
            picking_ids = sale_id.picking_ids.filtered(lambda x: x.state == 'done' and x.date_done)
            if sale_id:
                res.addenda_type = sale_id.addenda_type
                res.x_order_reference = sale_id.x_order_reference
                res.x_order_reference_date = sale_id.x_order_reference_date
                res.x_additional_reference = sale_id.x_additional_reference
                res.x_delivery_reference = sale_id.x_delivery_reference
                res.x_delivery_reference_date = sale_id.x_delivery_reference_date
                res.x_vendor_code = sale_id.x_vendor_code
                res.x_order_remision = sale_id.x_order_remision
                res.x_cedis_id = sale_id.x_cedis_id if sale_id.x_cedis_id else False
                res.x_cantidad_bultos = sale_id.x_cantidad_bultos
                res.x_tipo_moneda = sale_id.x_tipo_moneda
                res.x_tipo_bulto = sale_id.x_tipo_bulto
                if picking_ids:
                    x_order_remision = ""
                    for pick in picking_ids:
                        x_order_remision = pick.name.replace('/','-')
                    res.x_order_remision = x_order_remision
        return res


    def _l10n_mx_edi_cfdi_invoice_append_addenda(self, cfdi, addenda):
        ''' Append an additional block to the signed CFDI passed as parameter.
        :param move:    The account.move record.
        :param cfdi:    The invoice's CFDI as a string.
        :param addenda: (ir.ui.view) The addenda to add as a string.
        :return cfdi:   The cfdi including the addenda.
        '''
        if self.addenda_type != 'soriana_descarga':
            return super(AccountMove, self)._l10n_mx_edi_cfdi_invoice_append_addenda(cfdi, addenda)
        self.ensure_one()

        addenda_values = {'record': self, 'cfdi': cfdi}

        addenda = self.env['ir.qweb']._render(addenda.id, values=addenda_values).strip()
        if not addenda:
            return cfdi
        cfdi_node = etree.fromstring(cfdi)
        addenda_node = etree.fromstring(addenda)
        subnode_articulos = addenda_node.xpath('.//*[local-name()="Articulos"]')[0]
        ### Agregamos el Atributo de la Carta porte Prefix ####
        subnode_articulos.set('RowOrder', "0")

        version = cfdi_node.get('Version')

        # Add a root node Addenda if not specified explicitly by the user.
        if addenda_node.tag != '{http://www.sat.gob.mx/cfd/%s}Addenda' % version[0]:
            node = etree.Element(etree.QName('http://www.sat.gob.mx/cfd/%s' % version[0], 'Addenda'))
            node.append(addenda_node)
            addenda_node = node

        cfdi_node.append(addenda_node)
        return etree.tostring(cfdi_node, pretty_print=True, xml_declaration=True, encoding='UTF-8')



class AddendaOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    addenda_type = fields.Selection(selection_add=[('soriana_descarga', 'Soriana (Descarga Remision)')], ondelete={'soriana_descarga': 'set null'}) 

class AccountInvoiceLine(models.Model):
    _inherit = 'account.move.line'

    x_codigo_soriana = fields.Char('Codigo Soriana', related="product_id.x_codigo_soriana", readonly=False, store=True)

class SorianaCedisCode(models.Model):
    _name = 'soriana.cedis.code' 
    _description = 'Listado de CEDIS'
    
    name = fields.Char('Nombre', required=True)
    code = fields.Char('Código', required=True)