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

class AddendaSale(models.Model):
    """docstring for AddendaFields"""
    _inherit = 'sale.order'

    addenda_type = fields.Selection(selection_add=[('insabi', 'INSABI')], ondelete={'insabi': 'set null'}) 

    l10n_mx_edi_insabi_imss_no_orden = fields.Char('No. Orden', size=256)

    l10n_mx_edi_insabi_response_orden_remi = fields.Char('Orden Remi', size=256)

    l10n_mx_edi_insabi_final_destiny_clues = fields.Char('Entidad destino final (CLUES)', size=256)

    l10n_mx_edi_insabi_clue = fields.Char('CLUE', size=256)

    l10n_mx_edi_insabi_send_to_name = fields.Char('Razón Social o Nombre', size=256)

    l10n_mx_edi_insabi_contract_name = fields.Char(string='Número de Contrato', size=256)

    l10n_mx_edi_insabi_expedition_date = fields.Date('Fecha expedición', size=256)

    l10n_mx_edi_insabi_incoming_date = fields.Date('Fecha de entrega', size=256)

    l10n_mx_edi_insabi_reception_date = fields.Date('Fecha de recepción', size=256)


class AccountMove(models.Model):
    _inherit = 'account.move'

    addenda_type = fields.Selection(selection_add=[('insabi', 'INSABI')], ondelete={'insabi': 'set null'}) 

    l10n_mx_edi_insabi_imss_no_orden = fields.Char('No. Orden', size=256)

    l10n_mx_edi_insabi_response_orden_remi = fields.Char('Orden Remi', size=256)

    l10n_mx_edi_insabi_final_destiny_clues = fields.Char('Entidad destino final (CLUES)', size=256)

    l10n_mx_edi_insabi_clue = fields.Char('CLUE', size=256)

    l10n_mx_edi_insabi_send_to_name = fields.Char('Razón Social o Nombre', size=256)

    l10n_mx_edi_insabi_contract_name = fields.Char(string='Número de Contrato', size=256)

    l10n_mx_edi_insabi_expedition_date = fields.Date('Fecha de expedición', size=256)

    l10n_mx_edi_insabi_incoming_date = fields.Date('Fecha de entrega', size=256)

    l10n_mx_edi_insabi_reception_date = fields.Date('Fecha de recepción', size=256)

    @api.model
    def create(self, vals):
        res = super(AccountMove, self).create(vals)
        if res.move_type == 'out_invoice':
            sale_model = 'sale_line_ids' in res.invoice_line_ids._fields
            sale_id = res.mapped('invoice_line_ids.sale_line_ids.order_id') if sale_model else False
            if sale_id:
                res.addenda_type = sale_id.addenda_type
                res.l10n_mx_edi_insabi_imss_no_orden = sale_id.l10n_mx_edi_insabi_imss_no_orden
                res.l10n_mx_edi_insabi_response_orden_remi = sale_id.l10n_mx_edi_insabi_response_orden_remi
                res.l10n_mx_edi_insabi_final_destiny_clues = sale_id.l10n_mx_edi_insabi_final_destiny_clues
                res.l10n_mx_edi_insabi_clue = sale_id.l10n_mx_edi_insabi_clue
                res.l10n_mx_edi_insabi_send_to_name = sale_id.l10n_mx_edi_insabi_send_to_name
                res.l10n_mx_edi_insabi_contract_name = sale_id.l10n_mx_edi_insabi_contract_name
                res.l10n_mx_edi_insabi_expedition_date = sale_id.l10n_mx_edi_insabi_expedition_date
                res.l10n_mx_edi_insabi_incoming_date = sale_id.l10n_mx_edi_insabi_incoming_date
                res.l10n_mx_edi_insabi_reception_date = sale_id.l10n_mx_edi_insabi_reception_date
        return res

    def insabi_partner_send_address(self):
        shipTo = self.partner_shipping_id
        direccion_entrega = '%s %s %s, %s'%(shipTo.street_name or '', shipTo.street_number  or '', shipTo.l10n_mx_edi_colony  or '', shipTo.zip  or '')

        return direccion_entrega


    def insabi_partner_invoice_address(self):
        invoiceTo = self.partner_shipping_id
        direccion_factura = '%s %s %s, %s'%(invoiceTo.street_name or '', invoiceTo.street_number  or '', invoiceTo.l10n_mx_edi_colony  or '', invoiceTo.zip  or '')

        return direccion_factura

    def insabi_partner_invoice_address_extend(self):
        invoiceTo = self.partner_shipping_id
        direccion_factura = '%s %s %s, %s, %s'%(invoiceTo.street_name or '', invoiceTo.street_number  or '', invoiceTo.l10n_mx_edi_colony  or '', invoiceTo.zip  or '', invoiceTo.city or '')

        return direccion_factura

    def get_insabi_clue(self):
        insabi_clue_res  = ""
        if self.l10n_mx_edi_insabi_clue:
            insabi_clue_res = self.l10n_mx_edi_insabi_clue
        if self.l10n_mx_edi_insabi_send_to_name:
            insabi_clue_res = insabi_clue_res +' - ' +self.l10n_mx_edi_insabi_send_to_name if insabi_clue_res else self.l10n_mx_edi_insabi_send_to_name
        if self.l10n_mx_edi_insabi_final_destiny_clues:
            insabi_clue_res = insabi_clue_res +' - ' +self.l10n_mx_edi_insabi_final_destiny_clues if insabi_clue_res else self.l10n_mx_edi_insabi_final_destiny_clues
        return insabi_clue_res

    def get_format_date_insabi(self, date_info):
        if not date_info:
            return ''
        date_info = str(date_info)
        date_info_split = date_info.split('-')

        date_info_result = date_info_split[2]+'/'+date_info_split[1]+'/'+date_info_split[0]

        return date_info_result

class AccountInvoiceLine(models.Model):
    _inherit = 'account.move.line'

    def insabi_get_lot_name(self):
        lot_name = ""
        return lot_name

    def insabi_get_lot_expiration_date(self):
        expiration_date = ""
        return expiration_date

    def insabi_get_lot_creation_date(self):
        creation_date = ""
        return creation_date

    def insabi_get_aduana(self):
        aduana_name = ""
        return aduana_name

    def insabi_get_pedimento(self):
        pedimento_name = ""
        return pedimento_name

    def insabi_get_fecha_pedimento(self):
        fecha_pedimento = ""
        return fecha_pedimento

class AddendaOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    addenda_type = fields.Selection(selection_add=[('insabi', 'INSABI')], ondelete={'insabi': 'set null'}) 

