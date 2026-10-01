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

class ResPartner(models.Model):
    _inherit ='res.partner'

    l10n_mx_edi_walmart_gln = fields.Char(string='GLN', store=True, help='Global Location Number')
    l10n_mx_edi_walmart_supplier_code = fields.Char(string='Código de Proveedor', store=True)

class AddendaSale(models.Model):
    """docstring for AddendaFields"""
    _inherit = 'sale.order'

    addenda_type = fields.Selection(selection_add=[('walmart', 'Walmart')], ondelete={'walmart': 'set null'}) 

    l10n_mx_edi_walmart_order_name = fields.Char('Número de Pedido')
    l10n_mx_edi_walmart_date_order = fields.Date('Fecha Pedido')
    l10n_mx_edi_walmart_date_delivery = fields.Date('Fecha Entrega')
    l10n_mx_edi_walmart_notes = fields.Text('Comentarios')

    l10n_mx_edi_walmart_cedis = fields.Char('Clave CEDIS')

class AccountMove(models.Model):
    _inherit = 'account.move'
        
    def l10n_mx_edi_amece_is_required(self):
        addenda_amece = self.env.ref('l10n_mx_addenda_amece.l10n_mx_edi_addenda_amece', raise_if_not_found=False)
        addenda = (self.partner_id.l10n_mx_edi_addenda or self.partner_id.commercial_partner_id.l10n_mx_edi_addenda)
        return (True if addenda.id == addenda_amece.id else False)

    addenda_type = fields.Selection(selection_add=[('walmart', 'Walmart')], ondelete={'walmart': 'set null'}) 

    l10n_mx_edi_walmart_order_name = fields.Char('Número de Pedido')
    l10n_mx_edi_walmart_date_order = fields.Date('Fecha Pedido')
    l10n_mx_edi_walmart_date_delivery = fields.Date('Fecha Entrega')
    l10n_mx_edi_walmart_notes = fields.Text('Comentarios')
    l10n_mx_edi_walmart_cedis = fields.Char('Clave CEDIS')

    @api.model
    def create(self, vals):
        res = super(AccountMove, self).create(vals)
        if res.move_type == 'out_invoice':
            sale_model = 'sale_line_ids' in res.invoice_line_ids._fields
            sale_id = res.mapped('invoice_line_ids.sale_line_ids.order_id') if sale_model else False
            picking_ids = sale_id.picking_ids.filtered(lambda x: x.state == 'done' and x.date_done)
            if sale_id:
                res.addenda_type = sale_id.addenda_type
                res.l10n_mx_edi_walmart_order_name = sale_id.l10n_mx_edi_walmart_order_name
                res.l10n_mx_edi_walmart_date_order = sale_id.l10n_mx_edi_walmart_date_order
                res.l10n_mx_edi_walmart_date_delivery = sale_id.l10n_mx_edi_walmart_date_delivery
                res.l10n_mx_edi_walmart_notes = sale_id.l10n_mx_edi_walmart_notes
                res.l10n_mx_edi_walmart_cedis = sale_id.l10n_mx_edi_walmart_cedis

                # if picking_ids:
                #     x_order_remision = ""
                #     for pick in picking_ids:
                #         x_order_remision = pick.name.replace('/','-')
                #     res.x_order_remision = x_order_remision
        return res


    def _invoice_get_serie_and_folio_walmart(self, move):
        name_numbers = list(re.finditer('\d+', move.name))
        serie_number = move.name[:name_numbers[-1].start()]
        folio_number = name_numbers[-1].group().lstrip('0')
        return {
            'serie_number': serie_number,
            'folio_number': folio_number,
        }

    def getAddendaSumaryWalmart(self):
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

            serie_and_folio_res = self._invoice_get_serie_and_folio_walmart(self)
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

        walmart_notes = self.l10n_mx_edi_walmart_notes
        supplier_code = self.partner_id.l10n_mx_edi_walmart_supplier_code
        cedis = self.l10n_mx_edi_walmart_cedis
        res = {
                    'serie': Serie,
                    'folio': Folio,
                    'totalAmount': Total or 0.0,
                    'baseAmount': SubTotal or 0.0,
                    'taxAmount': TotalImpuestosTrasladados or 0.0,
                    'descuento': total_discount,
                    'walmart_notes': walmart_notes,
                    'supplier_code': supplier_code,
                    'cedis': cedis,
                }
        return res 



class AddendaOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    addenda_type = fields.Selection(selection_add=[('walmart', 'Walmart')], ondelete={'walmart': 'set null'}) 


class AccountInvoiceLine(models.Model):
    _inherit = 'account.move.line'
