# -*- coding: utf-8 -*-
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

# -*- coding: utf-8 -*-
from odoo import api, models, fields, tools, _
from odoo.tools.xml_utils import _check_with_xsd
from odoo.tools.float_utils import float_round, float_is_zero

import logging
import re
import base64
import json
import requests
import random
import string

from lxml import etree
from lxml.objectify import fromstring
from math import copysign
from datetime import datetime
from io import BytesIO
from zeep import Client
from zeep.transports import Transport
from json.decoder import JSONDecodeError

import sys

import logging
_logger = logging.getLogger(__name__)


parameter_limit = 800000

class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'


    # def _l10n_mx_edi_finkok_sign_payment(self, move, credentials, cfdi):
    #     return self.with_context(check_payment_size=True,move=move)._l10n_mx_edi_finkok_sign(move, credentials, cfdi)
        
    def _l10n_mx_edi_finkok_sign(self, credentials, cfdi):
        size_of_cfdi = sys.getsizeof(cfdi)
        _logger.info("\n##### TAMAÑO DEL CFDI: %s" % size_of_cfdi)
        _logger.info("\n##### CONTEXT: %s" % self._context)
        limit_weight_bytes_finkok = int(self.env['ir.config_parameter'].get_param('limit_weight_bytes_finkok',parameter_limit))
        if int(size_of_cfdi) > limit_weight_bytes_finkok:
            _logger.info("\n##### EL TAMAÑO DEL CFDI SUPERA EL LIMITE DE %s BYTES" % limit_weight_bytes_finkok)
            move = self._context.get('move', False)
            if move:
                credentials = {}
                company = move.company_id
                if company.l10n_mx_edi_pac_test_env:
                    credentials = {
                        'username': 'cfdi@vauxoo.com',
                        'password': 'vAux00__',
                        'sign_url': 'https://sftpdemo-facturacion.finkok.com/servicios/soap/stamp.wsdl',
                        'cancel_url': 'http://demo-facturacion.finkok.com/servicios/soap/cancel.wsdl',
                    }
                else:
                    if not company.sudo().l10n_mx_edi_pac_username or not company.sudo().l10n_mx_edi_pac_password:
                        return {
                            'errors': [_("The username and/or password are missing.")]
                        }

                    credentials  = {
                        'username': company.sudo().l10n_mx_edi_pac_username,
                        'password': company.sudo().l10n_mx_edi_pac_password,
                        'sign_url': 'https://extra-facturacion.finkok.com/servicios/soap/stamp.wsdl',
                        'cancel_url': 'http://facturacion.finkok.com/servicios/soap/cancel.wsdl',
                    }

            try:
                transport = Transport(timeout=20)
                client = Client(credentials['sign_url'], transport=transport)
                response = client.service.stamp(cfdi, credentials['username'], credentials['password'])
            except Exception as e:
                return {
                    'errors': [_("The Finkok service failed to sign with the following error: %s", str(e))],
                }

            if response.Incidencias and not response.xml:
                code = getattr(response.Incidencias.Incidencia[0], 'CodigoError', None)
                msg = getattr(response.Incidencias.Incidencia[0], 'MensajeIncidencia', None)
                errors = []
                if code:
                    errors.append(_("Code : %s") % code)
                if msg:
                    errors.append(_("Message : %s") % msg)
                return {'errors': errors}

            cfdi_signed = getattr(response, 'xml', None)
            if cfdi_signed:
                cfdi_signed = cfdi_signed.encode('utf-8')

            return {
                'cfdi_signed': cfdi_signed,
                'cfdi_encoding': 'str',
            }
        ####### Si no supera el limite regresamos el proceso estandar
        res = super(AccountEdiFormat, self)._l10n_mx_edi_finkok_sign_service(credentials, cfdi)
        return res