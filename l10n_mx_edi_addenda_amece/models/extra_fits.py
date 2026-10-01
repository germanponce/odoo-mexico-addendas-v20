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


class AddendaAmeceGLNPartner(models.Model):
    _name = 'addenda.amece.gln.partner'
    _description = 'GLN por Partner'
    _rec_name = 'l10n_mx_edi_amece_gln'

    company_id  = fields.Many2one('res.company', 'ID Ref')

    partner_id = fields.Many2one('res.partner', 'Cliente')

    l10n_mx_edi_amece_alternateid = fields.Char(
        string='Alternate Identification (Amece) ',
        help='Identificacion del proveedor (numero de proveedor asignado por el comprador)')

    l10n_mx_edi_amece_gln = fields.Char(
        string='Numero Global de Localización (GLN) ',
        help='Identificacion del proveedor (numero de proveedor asignado por el comprador)', size=13)   

class AddendaAmeceGTINProduct(models.Model):
    _name = 'addenda.amece.gtin.product'
    _description = 'GTIN por Producto'
    _rec_name = 'x_gtin_amece'

    partner_id = fields.Many2one('res.partner', 'Cliente')
    
    x_gtin_amece = fields.Char(string="Codigo EAN (GTIN)", size=128)

    product_template_id = fields.Many2one('product.template', 'Id Ref')

class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_mx_edi_amece_alternateid = fields.Char(
        string='Alternate Identification (Amece) ',
        help='Identificacion del proveedor (numero de proveedor asignado por el comprador)')

    l10n_mx_edi_amece_gln = fields.Char(
        string='Numero Global de Localización (GLN) ',
        help='Identificacion del proveedor (numero de proveedor asignado por el comprador)', size=13)    

    gln_code_ids = fields.One2many('addenda.amece.gln.partner', 'company_id', 'Codigos AMECE 7.1')


class ResCompany(models.Model):
    _inherit = 'res.partner'

    l10n_mx_edi_amece_gln = fields.Char(
        string='Numero Global de Localización (GLN) ',
        help='Identificacion del proveedor (numero de proveedor asignado por el comprador)', size=13)    

class AddendaProduct(models.Model):
    _inherit = 'product.template'

    gtin_code_ids = fields.One2many('addenda.amece.gtin.product', 'product_template_id', 'Codigos AMECE 7.1')

    x_gtin_amece = fields.Char(string="Codigo EAN (GTIN)",compute="_compute_x_gtin_amece",inverse="_set_x_gtin_amece", store=True)

    @api.depends('product_variant_ids.x_gtin_amece')
    def _compute_x_gtin_amece(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.x_gtin_amece = template.product_variant_ids.x_gtin_amece
        for template in (self - unique_variants):
            template.x_gtin_amece = False

    def _set_x_gtin_amece(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.x_gtin_amece = self.x_gtin_amece

class AddendaSale(models.Model):
    """docstring for AddendaFields"""
    _inherit = 'sale.order'

    addenda_type = fields.Selection(selection_add=[('amece', 'AMECE 7.1')], ondelete={'amece': 'set null'}) 

    l10n_mx_edi_amece_referenceidentification = fields.Char(string='Numero de pedido (comprador) ')
    l10n_mx_edi_amece_referencedate = fields.Date(string='Fecha del Pedido ')
    l10n_mx_edi_amece_additionalinformation = fields.Char(string='Numero de aprobacion')
    l10n_mx_edi_amece_personordepartmentname = fields.Char(string='Contacto de Compras')

    l10n_mx_edi_amece_shipto_id = fields.Many2one('res.partner', string='Entrega Mercancia ')

class AccountMove(models.Model):
    _inherit = 'account.move'
        

    def l10n_mx_edi_amece_is_required(self):
        addenda_amece = self.env.ref('l10n_mx_addenda_amece.l10n_mx_edi_addenda_amece', raise_if_not_found=False)
        addenda = (self.partner_id.l10n_mx_edi_addenda or self.partner_id.commercial_partner_id.l10n_mx_edi_addenda)
        return (True if addenda.id == addenda_amece.id else False)

    addenda_type = fields.Selection(selection_add=[('amece', 'AMECE 7.1')], ondelete={'amece': 'set null'}) 

    l10n_mx_edi_amece_referenceidentification = fields.Char(string='Numero de pedido (comprador) ')
    l10n_mx_edi_amece_referencedate = fields.Date(string='Fecha del Pedido ')
    l10n_mx_edi_amece_additionalinformation = fields.Char(string='Numero de aprobacion')
    l10n_mx_edi_amece_personordepartmentname = fields.Char(string='Contacto de Compras')

    l10n_mx_edi_amece_shipto_id = fields.Many2one('res.partner', string='Entrega Mercancia ')

    def get_l10n_mx_edi_amece_alternateid(self):
        l10n_mx_edi_amece_alternateid = self.company_id.l10n_mx_edi_amece_alternateid
        if self.company_id.gln_code_ids:
            for code in self.company_id.gln_code_ids:
                if code.partner_id.id == self.partner_id.id:
                    l10n_mx_edi_amece_alternateid = code.l10n_mx_edi_amece_alternateid
                    break
        return l10n_mx_edi_amece_alternateid

    def get_l10n_mx_edi_amece_gln(self):
        l10n_mx_edi_amece_gln = self.company_id.l10n_mx_edi_amece_gln
        if self.company_id.gln_code_ids:
            for code in self.company_id.gln_code_ids:
                if code.partner_id.id == self.partner_id.id:
                    l10n_mx_edi_amece_gln = code.l10n_mx_edi_amece_gln
                    break
        return l10n_mx_edi_amece_gln


    def getshipTostreetAddressOne(self, shipTo=False):
        streetAddressOne = '%s %s %s'%(shipTo.street_name or '', shipTo.street_number  or '', shipTo.l10n_mx_edi_colony  or '')
        return streetAddressOne

    def _invoice_get_serie_and_folio(self, move):
        name_numbers = list(re.finditer('\d+', move.name))
        serie_number = move.name[:name_numbers[-1].start()]
        folio_number = name_numbers[-1].group().lstrip('0')
        return {
            'serie_number': serie_number,
            'folio_number': folio_number,
        }

    def getAddendaSumary(self):
        Serie = ""
        Folio = ""       
        Total = ""
        SubTotal = ""
        Descuento = ""
        TipoCambio = ""
        TotalImpuestosTrasladados = ""
        cadena_original = ""

        for move in self:
            supplier_rfc = move.l10n_mx_edi_cfdi_supplier_rfc
            customer_rfc = move.l10n_mx_edi_cfdi_customer_rfc
            total = float_repr(move.l10n_mx_edi_cfdi_amount, precision_digits=move.currency_id.decimal_places)
            uuid = move.l10n_mx_edi_cfdi_uuid

            # If the CFDI attachment was unlinked from the edi_document (e.g. when canceling the invoice),
            # the l10n_mx_edi_cfdi_uuid, ... fields will have been set to False.
            # However, the attachment might still be there, so try to retrieve it.

            serie_and_folio_res = self._invoice_get_serie_and_folio(self)
            serie_number = serie_and_folio_res['serie_number']
            folio_number = serie_and_folio_res['folio_number']

            # ==== Invoice lines ====
            total_discount = 0.0
            for line in move.invoice_line_ids:
                amount_subtotal = line.price_unit * line.quantity
                amount_discount = (line.discount/100.0) * line.price_unit * line.quantity
                total_discount += amount_discount

            currency_conversion_rate = 1
            if move.currency_id.name == 'MXN':
                currency_conversion_rate = None
            else:
                # assumes that invoice.company_id.country_id.code == 'MX', as checked in '_is_required_for_invoice'
                currency_conversion_rate = abs(move.amount_total_signed) / abs(move.amount_total) if move.amount_total else 1

            Serie = serie_number
            Folio = folio_number
            Total = round(move.amount_total, 4)
            SubTotal = round(move.amount_untaxed, 4)
            Descuento = round(total_discount, 4)
            TipoCambio = currency_conversion_rate
            TotalImpuestosTrasladados = move.amount_tax
        res = {
                    'serie': Serie,
                    'folio': Folio,
                    'totalAmount': Total or 0.0,
                    'baseAmount': SubTotal or 0.0,
                    'taxAmount': TotalImpuestosTrasladados or 0.0,
                    'descuento': total_discount,
                }
        return res 


    @api.model
    def create(self, vals):
        res = super(AccountMove, self).create(vals)
        if res.move_type == 'out_invoice':
            sale_model = 'sale_line_ids' in res.invoice_line_ids._fields
            sale_id = res.mapped('invoice_line_ids.sale_line_ids.order_id') if sale_model else False
            if sale_id:
                res.addenda_type = sale_id.addenda_type
                res.l10n_mx_edi_amece_referenceidentification = sale_id.l10n_mx_edi_amece_referenceidentification
                res.l10n_mx_edi_amece_referencedate = sale_id.l10n_mx_edi_amece_referencedate
                res.l10n_mx_edi_amece_additionalinformation = sale_id.l10n_mx_edi_amece_additionalinformation
                res.l10n_mx_edi_amece_personordepartmentname = sale_id.l10n_mx_edi_amece_personordepartmentname
                res.l10n_mx_edi_amece_shipto_id = sale_id.l10n_mx_edi_amece_shipto_id.id if sale_id.l10n_mx_edi_amece_shipto_id else False
        return res

class AddendaOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    addenda_type = fields.Selection(selection_add=[('amece', 'AMECE 7.1')], ondelete={'amece': 'set null'}) 


class AccountInvoiceLine(models.Model):
    _inherit = 'account.move.line'

    def get_x_gtin_amece(self):
        x_gtin_amece = self.product_id.x_gtin_amece
        if self.product_id.gtin_code_ids:
            for code in self.product_id.gtin_code_ids:
                if code.partner_id.id == self.partner_id.id:
                    x_gtin_amece = code.x_gtin_amece
                    break
        return x_gtin_amece

    def getGrossPrice(self):
        precision_digits = self.currency_id.l10n_mx_edi_decimal_places
        if precision_digits is False:
            raise UserError(_(
                "The SAT does not provide information for the currency %s.\n"
                "You must get manually a key from the PAC to confirm the "
                "currency rate is accurate enough."), self.currency_id)

        subtotal_wo_discount = lambda l: float_round(
            l.price_subtotal / (1 - l.discount/100) if l.discount != 100 else
            l.price_unit * l.quantity, int(precision_digits))

        grossPrice = '%.*f' % (precision_digits, subtotal_wo_discount(self)/self.quantity) if self.quantity else 0.0                
        return float(grossPrice)

    def get_taxes_line_info(self):
        taxes_info = []
        tax_details = self.tax_ids.compute_all(
            self.price_unit,
            currency=self.currency_id,
            quantity=self.quantity,
            product=self.product_id,
            partner=self.partner_id,
            is_refund=self.move_id.move_type in ('out_refund', 'in_refund'),
        )

        for tax_res in tax_details['taxes']:
            if tax_res['base'] == 0:
                continue
            tax = self.env['account.tax'].browse(tax_res['id'])

            tax_rep_field = 'invoice_repartition_line_ids' if self.move_id.move_type == 'out_invoice' else 'refund_repartition_line_ids'
            tags = tax[tax_rep_field].tag_ids
            # tax_name = {'ISR': '001', 'IVA': '002', 'IEPS': '003'}.get(tags.name) if len(tags) == 1 else None
            tax_name = ""
            if tags:
                tax_name = tags[0].name
            # LAC = ISR
            # VAT = Impuesto sobre el valor
            # agregado (IVA)
            # GST = IEPS
            # AAA = Impuesto de Petróleo
            # AAD = Cigarros
            # FRE = Exento
            # LOC = Municipal
            # STT = Estatal
            # OTH = Otros Impuestos
            tax_name = {'ISR': 'LAC', 'IVA': 'VAT', 'IEPS': 'GST'}.get(tax_name) if tax_name else 'OTH'

            tax_vals = {
                            'tax': tax,
                            'base': tax_res['base'],
                            'tax_type': tax.l10n_mx_tax_type,
                            'tax_amount': tax.amount,
                            'tax_name': tax_name,
                            'total': tax_res['amount'],
                        }

            taxes_info.append(tax_vals)
        return taxes_info