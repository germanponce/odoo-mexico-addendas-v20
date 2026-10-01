# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright 2021 German Ponce Dominguez
#
##############################################################################


import base64
from itertools import groupby
import re
from datetime import datetime
from dateutil.relativedelta import relativedelta
from io import BytesIO
import requests
from pytz import timezone

from lxml import etree
from lxml.objectify import fromstring
from suds.client import Client

from odoo import _, api, fields, models, tools
from odoo.tools.xml_utils import _check_with_xsd
from odoo.tools import DEFAULT_SERVER_TIME_FORMAT
from odoo.tools import float_round
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_repr

import logging

_logger = logging.getLogger(__name__)


############# Herencia Ventas ####################

class AddendaPicking(models.Model):
    _inherit = 'stock.picking'

    addenda_type = fields.Selection(selection_add=[('pepsico', 'Pepsico')], ondelete={'pepsico': 'set null'}) 

class AddendaSale(models.Model):
    """docstring for AddendaFields"""
    _inherit = 'sale.order'

    addenda_type = fields.Selection(selection_add=[('pepsico', 'Pepsico')], ondelete={'pepsico': 'set null'}) 

    x_pepsico_idPedido = fields.Char('ID Pedido', size=64)
    x_payment_request = fields.Char('Solicitud de pago', size=64)
    x_reception = fields.Char('Número de recepción', size=64)

############# Herencia Factura ####################

class AccountMove(models.Model):
    _inherit ='account.move'

    addenda_type = fields.Selection(selection_add=[('pepsico', 'Pepsico')], ondelete={'pepsico': 'set null'}) 

    x_pepsico_idPedido = fields.Char('ID Pedido', size=64)
    x_payment_request = fields.Char('Solicitud de pago', size=64)
    x_reception = fields.Char('Número de recepción', size=64)

    def get_invoice_lines(self):
        return self.invoice_line_ids


    @api.model
    def create(self, vals):
        res = super(AccountMove, self).create(vals)
        if res.move_type == 'out_invoice':
            sale_model = 'sale_line_ids' in res.invoice_line_ids._fields
            sale_id = res.mapped('invoice_line_ids.sale_line_ids.order_id') if sale_model else False
            if sale_id:
                res.x_pepsico_idPedido = sale_id.x_pepsico_idPedido
                res.x_payment_request = sale_id.x_payment_request
                res.x_reception = sale_id.x_reception

        return res