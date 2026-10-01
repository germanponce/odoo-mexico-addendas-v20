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


from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round
from odoo.tools.float_utils import float_compare
import calendar

#### Gestión Zona Horaria ####

from datetime import datetime
from pytz import timezone
import pytz
import time
from datetime import timedelta

#### Gestión del Excel ####


import tempfile

import xlwt
from io import BytesIO
import base64

from itertools import zip_longest

import logging
_logger = logging.getLogger(__name__)

format_date = "%Y-%m-%d"

from odoo.addons.l10n_mx_edi.models.l10n_mx_edi_document import CFDI_DATE_FORMAT


class AccountPaymentCustomDateWizard(models.TransientModel):
    _name = 'account.payment.custom.date.wizard'
    _description = 'Asistente – Fecha Efectiva de Pago CFDI'

    cfdi_custom_date = fields.Datetime(
        string='Fecha Efectiva de Pago',
        required=True,
        default=lambda self: fields.Datetime.now(),
        help="Fecha y hora que se usará como FechaPago en el XML del "
             "complemento de pago. Se convierte automáticamente a la "
             "zona horaria fiscal del domicilio emisor.",
    )

    def write_custom_date(self):
        """Write the custom payment date to the selected account.payment records."""
        active_ids = self._context.get('active_ids', [])
        if not active_ids:
            return True
        payments = self.env['account.payment'].browse(active_ids)
        # cfdi_custom_date is a writable related field on account.payment
        # that points to move_id.cfdi_custom_date (see AccountMove below).
        payments.move_id.write({'cfdi_custom_date': self.cfdi_custom_date})
        return {'type': 'ir.actions.act_window_close'}

class AccountMove(models.Model):
    _inherit = 'account.move'

    cfdi_custom_date = fields.Datetime(
        string='Fecha Efectiva de Pago',
        copy=False,
        help="Si se establece, sobreescribe la FechaPago del XML del "
             "complemento de pago con esta fecha (convertida a la zona "
             "horaria fiscal del emisor). Déjelo vacío para usar la fecha "
             "contable del pago a las 12:00 horas (comportamiento estándar).",
    )

   #### Gestión Zona Horaria ####

    def _get_date_time_xml_tz(self):
        context = self._context
        res = {}
        dt_format = tools.DEFAULT_SERVER_DATETIME_FORMAT
        tz = self.env.user.tz
        if not tz:
            tz = 'Mexico/General'
        date_time_report_tz = ""
        for rec in self:
            htz_diff = rec._get_time_zone()
            date_time = str(rec.cfdi_custom_date) [0:19]if rec.cfdi_custom_date else datetime.now()
            custom_payment_date = time.strftime('%Y-%m-%d %H:%M:%S', time.strptime(str(date_time)[:19], '%Y-%m-%d %H:%M:%S'))
            custom_payment_date = datetime.strptime(custom_payment_date, '%Y-%m-%d %H:%M:%S') + timedelta(hours=htz_diff) or False
            custom_payment_date = str(custom_payment_date)
            date_time_report_tz = str(custom_payment_date)[0:19].replace(' ','T') if custom_payment_date else False
        return date_time_report_tz


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
    

    def _l10n_mx_edi_add_payment_cfdi_values(self, cfdi_values, pay_results):
        self.ensure_one()
        super()._l10n_mx_edi_add_payment_cfdi_values(cfdi_values, pay_results)

        # Bail out if the parent already detected errors.
        if cfdi_values.get('errors'):
            return

        if not self.cfdi_custom_date:
            return

        issued_address = cfdi_values.get('issued_address')
        if issued_address:
            tz = issued_address._l10n_mx_edi_get_cfdi_timezone()
        else:
            tz = timezone('America/Mexico_City')

        custom_dt_utc = self.cfdi_custom_date.replace(tzinfo=pytz.utc)
        custom_dt_local = custom_dt_utc.astimezone(tz).replace(tzinfo=None)

        cfdi_values['fecha_pago'] = custom_dt_local.strftime(CFDI_DATE_FORMAT)
        _logger.debug(
            "AccountMove %s: overriding fecha_pago with %s (UTC %s → %s)",
            self.id, cfdi_values['fecha_pago'], self.cfdi_custom_date, tz,
        )


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    cfdi_custom_date = fields.Datetime(
        related='move_id.cfdi_custom_date',
        string='Fecha Efectiva de Pago',
        readonly=False,
        copy=False,
        help="Fecha y hora que se usará como FechaPago en el complemento "
             "de pago del CFDI. Se convierte a la zona horaria fiscal del "
             "domicilio emisor al generar el XML.",
    )

   #### Gestión Zona Horaria ####

    def _get_date_time_xml_tz(self):
        context = self._context
        res = {}
        dt_format = tools.DEFAULT_SERVER_DATETIME_FORMAT
        tz = self.env.user.tz
        if not tz:
            tz = 'Mexico/General'
        date_time_report_tz = ""
        for rec in self:
            htz_diff = rec._get_time_zone()
            date_time = str(rec.cfdi_custom_date) [0:19]if rec.cfdi_custom_date else datetime.now()
            custom_payment_date = time.strftime('%Y-%m-%d %H:%M:%S', time.strptime(str(date_time)[:19], '%Y-%m-%d %H:%M:%S'))
            custom_payment_date = datetime.strptime(custom_payment_date, '%Y-%m-%d %H:%M:%S') + timedelta(hours=htz_diff) or False
            custom_payment_date = str(custom_payment_date)
            date_time_report_tz = str(custom_payment_date)[0:19].replace(' ','T') if custom_payment_date else False
        return date_time_report_tz


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

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    cfdi_custom_date = fields.Datetime(
        string='Fecha Efectiva de Pago',
        copy=False,
        help="Opcional. Si se establece, se usará como FechaPago en el "
             "complemento de pago del CFDI en lugar de la fecha contable "
             "del pago a las 12:00 horas.",
    )

    def _create_payment_vals_from_wizard(self, batch_result):
        res = super()._create_payment_vals_from_wizard(batch_result)
        if self.cfdi_custom_date:
            res['cfdi_custom_date'] = self.cfdi_custom_date
        return res
