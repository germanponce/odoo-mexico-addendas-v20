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

class PosPaymentMethod(models.Model):
    _name = 'pos.payment.method'
    _inherit ='pos.payment.method'

    payment_tpv_id = fields.Many2one('l10n_mx_edi.payment.method', 'Forma de Pago SAT')

class PosConfig(models.Model):
    _inherit = 'pos.config'

    automatic_validate = fields.Boolean('Validar Factura Automaticamente', default=True)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    automatic_validate = fields.Boolean('Validar Factura Automaticamente', related='pos_config_id.automatic_validate', readonly=False)

class PosOrder(models.Model):
    _name = 'pos.order'
    _inherit ='pos.order'

    def _prepare_invoice_vals(self):
        res = super(PosOrder, self)._prepare_invoice_vals()
        # if self.partner_id.vat and 'XAXX010101000' in self.partner_id.vat:# or 'XEXX010101000' in self.vat:
        #     res.update({
        #                     'l10n_mx_edi_usage': self.partner_id.l10n_mx_edi_usage,
        #                     'l10n_mx_edi_payment_policy': 'PUE',
        #                     'l10n_mx_edi_usage': 'S01',
        #                 })
        # else:
        #     res.update({
        #                     'l10n_mx_edi_usage': self.partner_id.l10n_mx_edi_usage,
        #                     'l10n_mx_edi_payment_policy': 'PUE',
        #                 })
        if self.session_id.config_id.automatic_validate:
            res.update({
                        'automatic_validate': True
                    })

        payment_tpv_id = False
        if self.payment_ids:
            payment_amount = 0.0
            payment_id = False
            for pay in self.payment_ids:
                if pay.amount > payment_amount:
                    payment_amount = pay.amount
                    payment_id = pay.payment_method_id

            if payment_id and payment_id.payment_tpv_id:
                payment_tpv_id = payment_id.payment_tpv_id
        if payment_tpv_id:
            res.update({
                'l10n_mx_edi_payment_method_id': payment_tpv_id.id,
                })
        if self.partner_id and self.partner_id.l10n_mx_edi_usage:
            res.update({
                'l10n_mx_edi_usage': self.partner_id.l10n_mx_edi_usage,
                })
        return res

class AccountMove(models.Model):
    _name = 'account.move'
    _inherit ='account.move'
    
    automatic_validate = fields.Boolean('Validar en Automatico')

    # def action_post(self):
    #     context = self._context
    #     result = super(AccountMove, self).action_post()
    #     self.env.cr.commit()
    #     for invoice in self:
    #         if invoice.move_type in ('out_invoice','out_refund'):
    #             if not invoice.cfdi_folio_fiscal and invoice.automatic_validate:
    #                 invoice.action_process_edi_web_services()

    #     return result  

    def _post(self, soft=True):
        result = super(AccountMove, self)._post(soft=soft)
        # self.env.cr.commit()
        for invoice in self:
            if invoice.move_type in ('out_invoice','out_refund'):
                if not invoice.cfdi_folio_fiscal and invoice.automatic_validate:
                    invoice.sudo().action_process_edi_web_services()
        return result  
