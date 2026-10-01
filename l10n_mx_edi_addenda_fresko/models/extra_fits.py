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



class AddendaSale(models.Model):
    """docstring for AddendaFields"""
    _inherit = 'sale.order'

    addenda_type = fields.Selection(selection_add=[('fresko_amc', 'Fresko AMC 7.1')], ondelete={'amece': 'set null'}) 

class AccountMove(models.Model):
    _inherit = 'account.move'
        
    def l10n_mx_edi_amece_is_required(self):
        addenda_amece = self.env.ref('l10n_mx_addenda_amece.l10n_mx_edi_addenda_amece', raise_if_not_found=False)
        addenda = (self.partner_id.l10n_mx_edi_addenda or self.partner_id.commercial_partner_id.l10n_mx_edi_addenda)
        return (True if addenda.id == addenda_amece.id else False)

    addenda_type = fields.Selection(selection_add=[('fresko_amc', 'Fresko AMC 7.1')], ondelete={'amece': 'set null'}) 

class AddendaOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    addenda_type = fields.Selection(selection_add=[('fresko_amc', 'Fresko AMC 7.1')], ondelete={'amece': 'set null'}) 


class AccountInvoiceLine(models.Model):
    _inherit = 'account.move.line'
