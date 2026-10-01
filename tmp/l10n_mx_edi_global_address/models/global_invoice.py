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

#### Gestión Zona Horaria ####

from datetime import datetime
from pytz import timezone
import pytz
import time
from datetime import timedelta


import logging
_logger = logging.getLogger(__name__)


class PosConfig(models.Model):
    _inherit = "pos.config"

    contact_global_id = fields.Many2one('res.partner', 'Dirección de Emisión (Factura Global)')
    emission_zip = fields.Char('Código Postal Emisión')
    global_sequence_id = fields.Many2one('ir.sequence', 'Secuencia de Facturas Globales')

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    contact_global_id = fields.Many2one('res.partner', 'Dirección de Emisión (Factura Global)', 
        related="pos_config_id.contact_global_id", readonly=False)

    emission_zip = fields.Char('Código Postal', 
        related="pos_config_id.emission_zip", readonly=False)

    global_sequence_id = fields.Many2one('ir.sequence', 'Secuencia de Facturas Globales',
        related="pos_config_id.global_sequence_id", readonly=False)


    @api.onchange('contact_global_id')
    def onchange_contact_global_id(self):
        if self.contact_global_id:
            self.emission_zip = self.contact_global_id.zip
    
class PosOrder(models.Model):
    _inherit ='pos.order'

    contact_global_id = fields.Many2one('res.partner', 'Dirección de Emisión (Factura Global)')
    emission_zip = fields.Char('Código Postal Emisión')

    payment_tpv_id = fields.Many2one('l10n_mx_edi.payment.method', 'Forma de Pago SAT')

    custom_edi_date = fields.Datetime('Fecha Factura Global')

    global_sequence_id = fields.Integer('ID Secuencia de Facturas Globales')

class L10nMxEdiGlobalInvoiceCreate(models.TransientModel):
    _inherit = 'l10n_mx_edi.global_invoice.create'


    @api.model  
    def default_get(self, fields):
        res = super(L10nMxEdiGlobalInvoiceCreate, self).default_get(fields)
        record_ids = self._context.get('active_ids', [])
        pos_order_obj = self.env['pos.order']
        if not record_ids:
            return {}
        tickets = []
        contact_global_id = False
        emission_zip = ''
        global_sequence_id = 0
        for ticket in pos_order_obj.browse(record_ids):
            contact_global_id = ticket.session_id.config_id.contact_global_id.id if ticket.session_id.config_id.contact_global_id else False
            emission_zip = ticket.session_id.config_id.emission_zip
            global_sequence_id = ticket.session_id.config_id.global_sequence_id.id if ticket.session_id.config_id.global_sequence_id else False
            break
        res.update(contact_global_id=contact_global_id, emission_zip=emission_zip, global_sequence_id=global_sequence_id)
        return res

    def _get_current_date_time(self):
        return fields.Datetime.now()

    contact_global_id = fields.Many2one('res.partner', 'Dirección de Emisión (Factura Global)')
    emission_zip = fields.Char('Código Postal Emisión')
    payment_tpv_id = fields.Many2one('l10n_mx_edi.payment.method', 'Forma de Pago SAT')
    custom_edi_date = fields.Datetime('Fecha Factura Global')
    global_sequence_id = fields.Integer('ID Secuencia de Facturas Globales')

    def action_create_global_invoice(self):
        # EXTENDS 'l10n_mx_edi'
        contact_global_id = self.contact_global_id
        emission_zip = self.emission_zip
        payment_tpv_id = self.payment_tpv_id
        custom_edi_date = self.custom_edi_date
        global_sequence_id = self.global_sequence_id
        self.ensure_one()
        if contact_global_id or emission_zip or payment_tpv_id or custom_edi_date or global_sequence_id:
            self.pos_order_ids.write({
                                        'contact_global_id': contact_global_id.id if contact_global_id else False,
                                        'emission_zip':emission_zip,
                                        'payment_tpv_id': payment_tpv_id.id if payment_tpv_id else False,
                                        'custom_edi_date': custom_edi_date,
                                        'global_sequence_id': global_sequence_id,
                                     })
        if self.pos_order_ids:
            self.pos_order_ids.with_context(contact_global_id=contact_global_id,emission_zip=emission_zip,payment_tpv_id=payment_tpv_id,custom_edi_date=custom_edi_date,global_sequence_id=global_sequence_id)._l10n_mx_edi_cfdi_global_invoice_try_send(periodicity=self.periodicity)
        else:
            super().with_context(contact_global_id=contact_global_id,emission_zip=emission_zip,payment_tpv_id=payment_tpv_id,custom_edi_date=custom_edi_date,global_sequence_id=global_sequence_id).action_create_global_invoice()

    @api.onchange('contact_global_id')
    def onchange_contact_global_id(self):
        if self.contact_global_id:
            self.emission_zip = self.contact_global_id.zip

class L10nMXEdiDocument(models.Model):
    _inherit = 'l10n_mx_edi.document'

    contact_global_id = fields.Many2one('res.partner', 'Dirección de Emisión (Factura Global)')
    emission_zip = fields.Char('Código Postal Emisión')
    payment_tpv_id = fields.Many2one('l10n_mx_edi.payment.method', 'Forma de Pago SAT')
    custom_edi_date = fields.Datetime('Fecha Factura Global')
    global_sequence_id = fields.Integer('ID Secuencia de Facturas Globales')

    def _action_retry_global_invoice_try_send(self):
        records = self._get_source_records()
        """ Retry the sending of a global invoice cfdi document that failed to be sent. """
        self.ensure_one()
        cfdi_infos = self._decode_cfdi_attachment(self.attachment_id.raw)
        if not cfdi_infos:
            return

        records = self._get_source_records()
        contact_global_id = records[0].contact_global_id
        emission_zip = records[0].emission_zip
        payment_tpv_id = records[0].payment_tpv_id
        custom_edi_date = records[0].custom_edi_date
        global_sequence_id = records[0].global_sequence_id
        records.with_context(contact_global_id=contact_global_id,emission_zip=emission_zip,payment_tpv_id=payment_tpv_id,custom_edi_date=custom_edi_date,global_sequence_id=global_sequence_id)._l10n_mx_edi_cfdi_global_invoice_try_send(
            periodicity=cfdi_infos['periodicity'],
            origin=self.attachment_origin,
        )

    def _create_update_global_invoice_document_from_pos_orders(self, orders, document_values):
        context = self._context
        document = super(L10nMXEdiDocument, self)._create_update_global_invoice_document_from_pos_orders(orders=orders, document_values=document_values)
        contact_global_id = context.get('contact_global_id',False)
        emission_zip = context.get('emission_zip','')
        payment_tpv_id = context.get('payment_tpv_id', False)
        custom_edi_date = context.get('custom_edi_date', False)
        global_sequence_id = context.get('global_sequence_id', 0)
        if contact_global_id:
            document.contact_global_id = contact_global_id.id
        if emission_zip:
            document.emission_zip = emission_zip
        if payment_tpv_id:
            document.payment_tpv_id = payment_tpv_id.id
        if custom_edi_date:
            document.custom_edi_date = custom_edi_date
        if global_sequence_id:
            document.global_sequence_id = global_sequence_id
        return document

    @api.model
    def _get_global_invoice_cfdi_sequence(self, company, create_if_missing=True):
        # v19 MIGRATION FIX (2026-07-06): el core v19 llama a este metodo con el kwarg
        # nuevo 'create_if_missing' (firma vieja v17 no lo tenia -> TypeError). Se agrega
        # a la firma y se reenvia a super para no romper la Factura Global.
        context = self._context
        global_sequence_id = context.get('global_sequence_id', 0)

        if global_sequence_id:
            global_sequence_br = self.env['ir.sequence'].browse(global_sequence_id)
            return global_sequence_br
        sequence = super(L10nMXEdiDocument, self)._get_global_invoice_cfdi_sequence(company, create_if_missing=create_if_missing)
        # """ Get or create the ir.sequence to be used to get the global invoice document name.

        # :param company: The company owning the sequence.
        # :return:        An ir.sequence record.
        # """
        # code = 'l10n_mx_global_invoice_cfdi'
        # sequence = self.env['ir.sequence'].sudo().search([('code', '=', code), ('company_id', '=', company.id)], limit=1)
        # if not sequence:
        #     sequence = self.env['ir.sequence'].sudo().create({
        #         'name': f"Global Invoice CFDI ({company.name})",
        #         'code': code,
        #         'company_id': company.id,
        #         'prefix': 'GINV/',
        #         'implementation': 'standard',
        #         'use_date_range': True,
        #         'padding': 5,
        #     })
        return sequence

    @api.model
    def _get_global_invoice_cfdi_values(self, cfdi_values_list, date, periodicity='04', origin=None):
        context = self._context
        # EXTENDS 'l10n_mx_edi'
        cfdi_values = super(L10nMXEdiDocument, self)._get_global_invoice_cfdi_values(cfdi_values_list=cfdi_values_list, date=date, periodicity=periodicity, origin=origin)
        contact_global_id = context.get('contact_global_id',False)
        emission_zip = context.get('emission_zip','')
        payment_tpv_id = context.get('payment_tpv_id', False)
        custom_edi_date = context.get('custom_edi_date', False)
        global_sequence_id = context.get('global_sequence_id', 0)
        if not contact_global_id and self.contact_global_id:
            contact_global_id = self.contact_global_id
        if not emission_zip and self.emission_zip:
            emission_zip = self.emission_zip
        if contact_global_id or emission_zip:
            if not emission_zip:
                emission_zip = contact_global_id.zip

            self.contact_global_id = contact_global_id.id
            self.emission_zip = emission_zip
            if emission_zip:
                cfdi_values['receptor']['domicilio_fiscal_receptor'] = emission_zip
                cfdi_values['lugar_expedicion'] = emission_zip
            # if contact_global_id.vat:
            #     cfdi_values['receptor']['rfc'] = contact_global_id.vat
            # if contact_global_id.zip:
            #     cfdi_values['receptor']['domicilio_fiscal_receptor'] = contact_global_id.zip
            #     cfdi_values['lugar_expedicion'] = contact_global_id.zip
        if payment_tpv_id:
            cfdi_values['forma_pago'] = payment_tpv_id.code

        if custom_edi_date:
            cfdi_global_date_with_tz = self._get_date_time_xml_tz(custom_edi_date)
            cfdi_values['fecha'] = cfdi_global_date_with_tz
        return cfdi_values


   #### Gestión Zona Horaria ####

    def _get_date_time_xml_tz(self, custom_edi_date):
        context = self._context
        res = {}
        dt_format = DEFAULT_SERVER_DATETIME_FORMAT
        tz = self.env.user.tz
        if not tz:
            tz = 'Mexico/General'
        date_time_2_tz = ""
        htz_diff = self._get_time_zone()
        date_time = str(custom_edi_date) [0:19] if custom_edi_date else datetime.now()
        custom_edi_mx_date = time.strftime('%Y-%m-%d %H:%M:%S', time.strptime(str(date_time)[:19], '%Y-%m-%d %H:%M:%S'))
        custom_edi_mx_date = datetime.strptime(custom_edi_mx_date, '%Y-%m-%d %H:%M:%S') + timedelta(hours=htz_diff) or False
        custom_edi_mx_date = str(custom_edi_mx_date)
        date_time_2_tz = str(custom_edi_mx_date)[0:19].replace(' ','T') if custom_edi_mx_date else False
        return date_time_2_tz


    def _get_time_zone(self):

        userstz = self.env.user.tz
        if not userstz:
            userstz = 'Mexico/General'
        a = 0
        if userstz:
            hours = timezone(userstz)
            fmt = '%Y-%m-%d %H:%M:%S %Z%z'
            now = datetime.now()
            loc_dt = hours.localize(datetime(now.year, now.month, now.day,
                                             now.hour, now.minute, now.second))
            timezone_loc = (loc_dt.strftime(fmt))
            diff_timezone_original = timezone_loc[-5:-2]
            timezone_original = int(diff_timezone_original)
            s = str(datetime.now(pytz.timezone(userstz)))
            s = s[-6:-3]
            timezone_present = int(s)*-1
            a = timezone_original + ((
                timezone_present + timezone_original)*-1)
        return a
    
    ############################ 
