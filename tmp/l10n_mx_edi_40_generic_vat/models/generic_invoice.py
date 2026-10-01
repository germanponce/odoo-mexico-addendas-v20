# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright 2021 German Ponce Dominguez
#
##############################################################################

from odoo import models, api, fields, _
from odoo.exceptions import ValidationError, UserError

from odoo.tools import float_is_zero, float_compare
from itertools import groupby
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from datetime import datetime

import logging
_logger = logging.getLogger(__name__)


############# Contactos ####################
class ResPartner(models.Model):
    _inherit ='res.partner'


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit ='account.move'

    fg_periodicity = fields.Selection(
        selection=[('01', '01 - Diario'),
                   ('02', '02 - Semanal'),
                   ('03', '03 - Quincenal'),
                   ('04', '04 - Mensual'),
                   ('05', '05 - Bimestral'),],
        string=_('Periodicidad'),
    )

    fg_months = fields.Selection(
        selection=[('01', '01 - Enero'),
                   ('02', '02 - Febrero'),
                   ('03', '03 - Marzo'),
                   ('04', '04 - Abril'),
                   ('05', '05 - Mayo'),
                   ('06', '06 - Junio'),
                   ('07', '07 - Julio'),
                   ('08', '08 - Agosto'),
                   ('09', '09 - Septiembre'),
                   ('10', '10 - Octubre'),
                   ('11', '11 - Noviembre'),
                   ('12', '12 - Diciembre'),
                   ('13', '13 - Enero - Febrero'),
                   ('14', '14 - Marzo - Abril'),
                   ('15', '15 - Mayo - Junio'),
                   ('16', '16 - Julio - Agosto'),
                   ('17', '17 - Septiembre - Octubre'),
                   ('18', '18 - Noviembre - Diciembre'),],
        string=_('Meses'),
    )

    fg_year =  fields.Char(string=_('Año'))

    def get_edi_receptor_dynamic_info(self, edi_attr, current_info):
        description_edi = ""
        invoice_general_public = self.l10n_mx_edi_cfdi_to_public
        if not invoice_general_public:
            if self.partner_id.vat:
                if 'XAXX010101000' in self.partner_id.vat:
                    invoice_general_public = True 
        if edi_attr == 'rfc':
            if current_info:
                description_edi = current_info
            if invoice_general_public:
                description_edi = 'XAXX010101000'
        if edi_attr == 'codigopostalreceptor':
            if current_info:
                description_edi = current_info
            if invoice_general_public:
                issued_address = self.partner_id
                if issued_address.parent_id:
                    issued_address = issued_address.parent_id
                description_edi =issued_address.zip
        if edi_attr == 'usocfdi':
            if current_info:
                description_edi = current_info
            if invoice_general_public:
                description_edi = 'S01'
            else:
                if self.l10n_mx_edi_usage == 'P01' and current_info == 'S01':
                    description_edi = 'P01'
                    raise UserError("El codigo P01 ya no se encuentra vigente.")
        if edi_attr == 'regimenfiscalreceptor':
            if current_info:
                description_edi = current_info
            if invoice_general_public:
                description_edi = '616'
        if edi_attr == 'nombre':
            if current_info:
                description_edi = current_info
            if invoice_general_public:
                description_edi = 'PUBLICO EN GENERAL'

        if edi_attr == 'metodopago':
            if current_info:
                description_edi = current_info
            if invoice_general_public:
                description_edi = 'PUE'
            if self.amount_total <= 0.0:
                description_edi = False

        if edi_attr == 'condicionesdepago':
            if current_info:
                description_edi = current_info
            if invoice_general_public:
                description_edi = 'Contado'
                description_edi = 'Pago de Contado'
            if self.amount_total <= 0.0:
                description_edi = False
        if not description_edi:
            return False
        return description_edi

    def _l10n_mx_edi_add_invoice_cfdi_values(self, cfdi_values, percentage_paid=None, global_invoice=False):        
        # EXTENDS 'l10n_mx_edi'
        self.ensure_one()
        super()._l10n_mx_edi_add_invoice_cfdi_values(cfdi_values)
        if cfdi_values.get('errors'):
            return

        cfdi_values['record'] = self
        cfdi_values['metodo_pago'] = self.get_edi_receptor_dynamic_info('metodopago', cfdi_values['metodo_pago'])
        cfdi_values['condiciones_de_pago'] = self.get_edi_receptor_dynamic_info('condicionesdepago', cfdi_values['condiciones_de_pago'])
        cfdi_values['receptor']['rfc'] = self.get_edi_receptor_dynamic_info('rfc', cfdi_values['receptor']['rfc'])
        cfdi_values['receptor']['domicilio_fiscal_receptor'] = self.get_edi_receptor_dynamic_info('codigopostalreceptor', cfdi_values['receptor']['domicilio_fiscal_receptor'])
        cfdi_values['receptor']['regimen_fiscal_receptor'] = self.get_edi_receptor_dynamic_info('regimenfiscalreceptor', cfdi_values['receptor']['regimen_fiscal_receptor'])
        cfdi_values['receptor']['uso_cfdi'] = self.get_edi_receptor_dynamic_info('usocfdi', cfdi_values['receptor']['uso_cfdi'])
        cfdi_values['receptor']['nombre'] = self.get_edi_receptor_dynamic_info('nombre', cfdi_values['receptor']['nombre'])
        if self.l10n_mx_edi_cfdi_to_public and self.move_type == 'out_invoice':
            information_global = cfdi_values.get('information_global', {})
            if not information_global:
                global_vals = {
                                'periodicidad': self.fg_periodicity if self.fg_periodicity else '01',
                                'meses': self.fg_months,
                                'ano': self.fg_year,
                              }
                cfdi_values['information_global'] = global_vals

# -------------------------------------------------------------------------
    # CFDI Generation: Payments
    # -------------------------------------------------------------------------

    def _l10n_mx_edi_add_payment_cfdi_values(self, cfdi_values, pay_results):

        # EXTENDS 'l10n_mx_edi'
        self.ensure_one()
        super()._l10n_mx_edi_add_payment_cfdi_values(cfdi_values, pay_results=pay_results)
        if cfdi_values.get('errors'):
            return
        cfdi_values['record'] = self


class AccountPayment(models.Model):
    _inherit ='account.payment'

    def get_edi_receptor_dynamic_info(self, edi_attr, current_info):
        description_edi = ""
        invoice_general_public = self.l10n_mx_edi_cfdi_to_public
        if self.partner_id.vat:
            if 'XAXX010101000' in self.partner_id.vat:
                invoice_general_public = True 
        if edi_attr == 'rfc':
            if current_info:
                description_edi = current_info
            if invoice_general_public:
                description_edi = 'XAXX010101000'
        if edi_attr == 'codigopostalreceptor':
            if current_info:
                description_edi = current_info
            if invoice_general_public:
                issued_address = self.partner_id
                if issued_address.parent_id:
                    issued_address = issued_address.parent_id
                description_edi =issued_address.zip
        if edi_attr == 'usocfdi':
            if current_info:
                description_edi = current_info
            if invoice_general_public:
                description_edi = 'S01'
        if edi_attr == 'regimenfiscalreceptor':
            if current_info:
                description_edi = current_info
            if invoice_general_public:
                description_edi = '616'
        if edi_attr == 'nombre':
            if current_info:
                description_edi = current_info
            if invoice_general_public:
                description_edi = 'PUBLICO EN GENERAL'
        return description_edi
